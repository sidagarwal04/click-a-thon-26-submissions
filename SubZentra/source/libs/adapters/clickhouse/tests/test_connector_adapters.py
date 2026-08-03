"""The connector adapters, tested without a ClickHouse instance.

Two things are worth asserting here and one is not. Worth asserting: that the
adapters satisfy the application's Protocols by shape, and that the pure logic
around the driver — identifier quoting, failure classification, type inference,
credential sealing — behaves. Not worth asserting here: that the SQL returns the
right answers, which needs a live instance and belongs in an integration test.

That gap is deliberate and known: real dialect and ``system.*`` behaviour is
unverified by this suite.
"""

from __future__ import annotations

import inspect
import os

import pytest
from zentra_application_connector import (
    CredentialCipher,
    FileLandingZone,
    SourceConnector,
    SourceCredentials,
)
from zentra_domain_connector import ConnectionFailure

from zentra_adapter_clickhouse.cipher import (
    AesGcmCredentialCipher,
    CredentialSealError,
)
from zentra_adapter_clickhouse.landing_zone import (
    ClickHouseLandingZone,
    _arrow_to_clickhouse,
    _infer_type,
    _sanitise_identifier,
)
from zentra_adapter_clickhouse.source_connector import (
    ClickHouseSourceConnector,
    _classify_failure,
)
from zentra_adapter_clickhouse.sql import qualify, quote_identifier

CREDENTIALS = SourceCredentials(
    host="warehouse.example",
    port=8443,
    database="tpch",
    username="reader",
    password="s3cret",
)


def _assert_conforms(adapter: object, protocol: type) -> None:
    """Assert an adapter implements a Protocol method-for-method.

    ``isinstance`` against a Protocol needs ``@runtime_checkable`` and even then
    compares only method *names*. Comparing signatures is what actually catches
    the failure worth catching: a port gaining an argument that its adapter did
    not, which type checking alone would not surface until something called it.
    """
    for name, declared in inspect.getmembers(protocol, inspect.isfunction):
        if name.startswith("_"):
            continue
        implemented = getattr(adapter, name, None)
        assert implemented is not None, f"{adapter!r} is missing {name}()"
        expected = list(inspect.signature(declared).parameters)[1:]
        actual = list(inspect.signature(implemented).parameters)
        assert actual == expected, f"{name}() takes {actual}, port declares {expected}"


def test_source_connector_conforms_to_its_port() -> None:
    _assert_conforms(ClickHouseSourceConnector(), SourceConnector)


def test_landing_zone_conforms_to_its_port() -> None:
    zone = ClickHouseLandingZone(host="h", port=8443, username="u", password="p")
    _assert_conforms(zone, FileLandingZone)


def test_cipher_conforms_to_its_port() -> None:
    _assert_conforms(AesGcmCredentialCipher(os.urandom(32)), CredentialCipher)


# ------------------------------------------------------------------ quoting


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("orders", "`orders`"),
        ("order count", "`order count`"),
        ("we`ird", "`we``ird`"),
    ],
)
def test_identifiers_are_quoted_and_escaped(raw: str, expected: str) -> None:
    """Identifiers cannot be parameterised, so this is the injection boundary."""
    assert quote_identifier(raw) == expected


def test_a_backtick_injection_attempt_stays_inside_the_quotes() -> None:
    hostile = "x` FROM system.users --"
    quoted = quote_identifier(hostile)
    assert quoted.startswith("`") and quoted.endswith("`")
    assert "``" in quoted


def test_qualified_names_escape_both_halves() -> None:
    """The landing zone once inlined raw backticks here; both halves must escape."""
    assert qualify("db`x", "t`y") == "`db``x`.`t``y`"


# --------------------------------------------------------------- failures


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("Authentication failed for user", ConnectionFailure.AUTHENTICATION_FAILED),
        ("Access denied", ConnectionFailure.AUTHENTICATION_FAILED),
        ("Database tpch does not exist", ConnectionFailure.DATABASE_NOT_FOUND),
        ("connection refused", ConnectionFailure.UNREACHABLE),
        ("timed out", ConnectionFailure.UNREACHABLE),
    ],
)
def test_driver_errors_map_to_actionable_failures(
    message: str, expected: ConnectionFailure
) -> None:
    assert _classify_failure(RuntimeError(message)) is expected


# ---------------------------------------------------------- csv inference


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        (["1", "2", "3"], "Nullable(Int64)"),
        (["-1", "42"], "Nullable(Int64)"),
        (["1.5", "2.25"], "Nullable(Float64)"),
        (["2026-01-01", "2026-02-03"], "Nullable(Date)"),
        (["alice", "bob"], "Nullable(String)"),
        ([], "Nullable(String)"),
        (["1", "alice"], "Nullable(String)"),
    ],
)
def test_csv_types_are_inferred_conservatively(
    values: list[str], expected: str
) -> None:
    """A wrong String costs one correction; a wrong Int64 costs a failed load."""
    assert _infer_type(values) == expected


def test_every_inferred_type_is_nullable() -> None:
    """One blank cell in row 40,000 must not fail a load the user approved."""
    assert _infer_type(["1", "2"]).startswith("Nullable(")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("customer id", "customer_id"),
        ("Customer-ID!", "Customer_ID"),
        ("2024_total", "c_2024_total"),
        ("", "column"),
        ("   ", "column"),
    ],
)
def test_file_column_names_are_made_safe(raw: str, expected: str) -> None:
    """A finance team's export should not need renaming before it is usable."""
    assert _sanitise_identifier(raw) == expected


def test_arrow_types_map_to_nullable_clickhouse_types() -> None:
    import pyarrow as pa

    assert _arrow_to_clickhouse(pa.int32()) == "Nullable(Int64)"
    assert _arrow_to_clickhouse(pa.float64()) == "Nullable(Float64)"
    assert _arrow_to_clickhouse(pa.bool_()) == "Nullable(Bool)"
    assert _arrow_to_clickhouse(pa.string()) == "Nullable(String)"
    assert _arrow_to_clickhouse(pa.decimal128(10, 2)) == "Nullable(Decimal(10, 2))"


# ------------------------------------------------------------------ cipher


def test_sealed_credentials_do_not_contain_the_password() -> None:
    cipher = AesGcmCredentialCipher(os.urandom(32))

    sealed = cipher.seal(CREDENTIALS)

    assert CREDENTIALS.password.encode() not in sealed
    assert CREDENTIALS.username.encode() not in sealed


def test_sealing_round_trips() -> None:
    cipher = AesGcmCredentialCipher(os.urandom(32))

    assert cipher.open(cipher.seal(CREDENTIALS)) == CREDENTIALS


def test_sealing_the_same_credentials_twice_differs() -> None:
    """A fresh nonce per seal; reuse under one key is what breaks GCM."""
    cipher = AesGcmCredentialCipher(os.urandom(32))

    assert cipher.seal(CREDENTIALS) != cipher.seal(CREDENTIALS)


def test_a_tampered_ciphertext_fails_to_open() -> None:
    """Authenticated, so tampering fails rather than yielding a usable target."""
    cipher = AesGcmCredentialCipher(os.urandom(32))
    sealed = bytearray(cipher.seal(CREDENTIALS))
    sealed[-1] ^= 0x01

    with pytest.raises(CredentialSealError):
        cipher.open(bytes(sealed))


def test_a_different_key_cannot_open() -> None:
    sealed = AesGcmCredentialCipher(os.urandom(32)).seal(CREDENTIALS)

    with pytest.raises(CredentialSealError):
        AesGcmCredentialCipher(os.urandom(32)).open(sealed)


def test_a_truncated_seal_is_rejected() -> None:
    cipher = AesGcmCredentialCipher(os.urandom(32))

    with pytest.raises(CredentialSealError):
        cipher.open(b"short")


@pytest.mark.parametrize("length", [8, 20, 64])
def test_an_invalid_key_length_is_refused(length: int) -> None:
    with pytest.raises(ValueError, match="16, 24, or 32 bytes"):
        AesGcmCredentialCipher(os.urandom(length))


def test_a_missing_key_raises_rather_than_generating_one(monkeypatch) -> None:
    """A generated key works until restart, then orphans every credential."""
    monkeypatch.delenv("CONNECTOR_CREDENTIAL_KEY", raising=False)

    with pytest.raises(ValueError, match="is not set"):
        AesGcmCredentialCipher.from_env()


def test_a_key_is_read_from_the_environment(monkeypatch) -> None:
    monkeypatch.setenv("CONNECTOR_CREDENTIAL_KEY", os.urandom(32).hex())

    cipher = AesGcmCredentialCipher.from_env()

    assert cipher.open(cipher.seal(CREDENTIALS)) == CREDENTIALS


# ------------------------------------------------------- overlap measurement


class _StubClient:
    """A client that returns one prepared row, so SQL is not under test here."""

    def __init__(self, row: tuple) -> None:
        self.row = row

    def query(self, sql: str, parameters: dict | None = None):
        return type("Result", (), {"result_rows": [self.row]})()


def test_sample_size_reflects_the_smaller_side(monkeypatch) -> None:
    """The ceiling must bound confidence by the *weakest* evidence.

    Regression: this reported the larger side, so a 50-row lookup joined against
    20,000 fact rows claimed a 20,000-row sample and lifted the sample-size
    ceiling to 1.0 on evidence that did not support it.
    """
    connector = ClickHouseSourceConnector()
    # left_distinct, right_distinct, matched, left_rows, right_rows
    monkeypatch.setattr(
        connector, "_connect", lambda creds: _StubClient((50, 900, 50, 50, 20_000))
    )

    overlap = connector._overlap_single_instance(
        CREDENTIALS, ("db", "lookup", "id"), ("db", "facts", "lookup_id"), 10_000
    )

    assert overlap.sampled_rows == 50


def test_uniqueness_is_derived_per_side(monkeypatch) -> None:
    """Direction depends on which side is unique, so each is judged separately."""
    connector = ClickHouseSourceConnector()
    monkeypatch.setattr(
        connector, "_connect", lambda creds: _StubClient((50, 900, 50, 50, 20_000))
    )

    overlap = connector._overlap_single_instance(
        CREDENTIALS, ("db", "lookup", "id"), ("db", "facts", "lookup_id"), 10_000
    )

    assert overlap.left_is_unique is True
    assert overlap.right_is_unique is False
