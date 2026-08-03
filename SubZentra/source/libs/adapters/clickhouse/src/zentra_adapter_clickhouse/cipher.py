"""Sealing source credentials before they reach storage.

AES-GCM rather than a plain cipher because it is authenticated: a tampered
ciphertext fails to open rather than decrypting to something the connector
would then try to connect with.

Lives in the ClickHouse adapter package because that is where the credentials
are consumed, but it holds no ClickHouse specifics — a second source type would
reuse it unchanged.
"""

from __future__ import annotations

import json
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from zentra_application_connector import SourceCredentials

#: GCM's standard nonce length. Prepended to the ciphertext so that opening
#: needs only the key, and generated fresh per seal — reusing a nonce under the
#: same key is the one mistake that breaks GCM outright.
NONCE_BYTES = 12

#: Bound to the ciphertext but not encrypted. If a stored row is moved to a
#: different column or a different purpose, opening it fails rather than
#: silently succeeding somewhere it was never meant to be used.
_ASSOCIATED_DATA = b"zentra:connector:source-credentials:v1"


class CredentialSealError(ValueError):
    """A sealed credential could not be opened."""


class AesGcmCredentialCipher:
    """A ``CredentialCipher`` over AES-GCM with a key from the environment."""

    def __init__(self, key: bytes) -> None:
        if len(key) not in (16, 24, 32):
            raise ValueError(
                "Credential encryption key must be 16, 24, or 32 bytes"
            )
        self._aes = AESGCM(key)

    @classmethod
    def from_env(
        cls, variable: str = "CONNECTOR_CREDENTIAL_KEY"
    ) -> AesGcmCredentialCipher:
        """Build from a hex-encoded key in the environment.

        Raises rather than generating a key when the variable is missing. A
        generated key would work perfectly until the process restarted, at which
        point every stored credential would become permanently unopenable — a
        failure that surfaces long after the mistake that caused it.
        """
        raw = os.environ.get(variable)
        if not raw:
            raise ValueError(
                f"{variable} is not set; connector credentials cannot be sealed"
            )
        return cls(bytes.fromhex(raw))

    def seal(self, credentials: SourceCredentials) -> bytes:
        payload = json.dumps(
            {
                "host": credentials.host,
                "port": credentials.port,
                "database": credentials.database,
                "username": credentials.username,
                "password": credentials.password,
                "secure": credentials.secure,
            }
        ).encode()
        nonce = os.urandom(NONCE_BYTES)
        return nonce + self._aes.encrypt(nonce, payload, _ASSOCIATED_DATA)

    def open(self, sealed: bytes) -> SourceCredentials:
        if len(sealed) <= NONCE_BYTES:
            raise CredentialSealError("Sealed credential is malformed")
        nonce, ciphertext = sealed[:NONCE_BYTES], sealed[NONCE_BYTES:]
        try:
            payload = self._aes.decrypt(nonce, ciphertext, _ASSOCIATED_DATA)
        except Exception as exc:  # noqa: BLE001 - the library's failure is opaque
            raise CredentialSealError(
                "Sealed credential could not be opened"
            ) from exc
        data = json.loads(payload)
        return SourceCredentials(**data)
