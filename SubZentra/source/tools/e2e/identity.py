"""Signing keys and bound identities for the browser journeys.

The API verifies bearer tokens by fetching `{CLERK_ISSUER}/.well-known/jwks.json`
and checking an RS256 signature. Nothing in that path is Clerk-specific: point
the issuer at a local static server holding a key we generated, and the real
verifier, the real identity resolution, and the real RLS all run unchanged.
That is the point — the journeys are supposed to prove the authorization path,
so stubbing it out would remove the thing under test.

What this deliberately does *not* prove is Clerk's own login flow. That is a
third party's correctness, it needs their secrets in CI, and it would make the
suite fail when their status page is red. The seam is drawn at the token: we
assert everything from the token inward.

Four identities are bound rather than one, because half the acceptance criteria
are about what a role may *not* do, and a suite that only ever signs in as an
owner cannot show that.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

#: One organization, four memberships. Every journey runs against the same
#: Tenant so that a role difference is the only variable.
ORGANIZATION_ID = "org_e2e_forensic_observatory"

ROLES = ("owner", "admin", "member", "viewer")

#: Long enough that a slow CI run cannot expire a token mid-journey, short
#: enough that a leaked artifact is not a standing key. These never leave the
#: runner.
TOKEN_LIFETIME = timedelta(hours=4)

_KEY_ID = "zentra-e2e"


def subject_id(role: str) -> str:
    return f"user_e2e_{role}"


def tenant_id():
    """The same derivation `bootstrap()` uses, so the rows line up."""
    return uuid5(NAMESPACE_URL, f"zentraos:clerk:tenant:{ORGANIZATION_ID}")


def user_id(role: str):
    return uuid5(NAMESPACE_URL, f"zentraos:clerk:user:{subject_id(role)}")


@dataclass(frozen=True, slots=True)
class SigningKey:
    private_pem: bytes
    jwks: dict

    @classmethod
    def generate(cls) -> SigningKey:
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        private_pem = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        public_jwk = json.loads(
            jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key())
        )
        public_jwk.update({"kid": _KEY_ID, "use": "sig", "alg": "RS256"})
        return cls(private_pem=private_pem, jwks={"keys": [public_jwk]})


def mint(key: SigningKey, *, issuer: str, role: str) -> str:
    """A token the API's own verifier will accept.

    `org_id` rather than the nested `o.id` form: the verifier reads both, and
    exercising the flat one keeps this honest about which claim the journeys
    depend on.
    """
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": subject_id(role),
            "org_id": ORGANIZATION_ID,
            "iss": issuer,
            "iat": now,
            "exp": now + TOKEN_LIFETIME,
        },
        key.private_pem,
        algorithm="RS256",
        headers={"kid": _KEY_ID},
    )


def write_jwks(key: SigningKey, directory: Path) -> Path:
    """Lay the JWKS out where a plain static file server will serve it.

    `python -m http.server` over this directory answers exactly the path
    `PyJWKClient` asks for, which is cheaper and more predictable than running
    another application.
    """
    well_known = directory / ".well-known"
    well_known.mkdir(parents=True, exist_ok=True)
    path = well_known / "jwks.json"
    path.write_text(json.dumps(key.jwks, indent=2))
    return path


async def bind_identities(owner_url: str) -> None:
    """Create the Tenant, the four users, and their memberships.

    Reuses `bootstrap()` rather than reimplementing the upserts, so the rows the
    journeys authenticate against are made the same way a real deployment makes
    them. Idempotent: ids are derived, and re-running is a no-op.
    """
    from zentra_adapter_postgres.bootstrap import bootstrap

    for role in ROLES:
        os.environ.update(
            {
                "DATABASE_OWNER_URL": owner_url,
                "CLERK_ORGANIZATION_ID": ORGANIZATION_ID,
                "CLERK_USER_ID": subject_id(role),
                "BOOTSTRAP_ROLE": role,
                "BOOTSTRAP_TENANT_NAME": "Forensic Observatory E2E",
                "BOOTSTRAP_USER_EMAIL": f"{role}@e2e.zentraos.test",
            }
        )
        await bootstrap()
