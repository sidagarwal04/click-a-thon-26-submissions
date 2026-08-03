from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt

# Minted per call/per short-lived construction, never cached long-term, so a
# short expiry costs nothing and keeps a leaked token useless quickly.
TOKEN_TTL = timedelta(minutes=5)


def mint_cube_token(
    tenant_id: str | None,
    data_connection_id: str | None,
    relation_fingerprint: str | None,
    *,
    secret: str,
) -> str:
    """Sign the securityContext Cube's checkAuth will verify.

    `tenant_id`/`data_connection_id` absent means the demo warehouse: Cube's
    contextToAppId falls back to a single shared appId in that case. When
    present, `relation_fingerprint` is what actually invalidates a tenant's
    compiled schema on a Relation confirmation/rejection — the catalog
    version alone does not change when a Relation's state changes under it.
    """
    now = datetime.now(UTC)
    claims = {
        "tenantId": tenant_id,
        "dataConnectionId": data_connection_id,
        "relationFingerprint": relation_fingerprint,
        "iat": now,
        "exp": now + TOKEN_TTL,
    }
    return jwt.encode(claims, secret, algorithm="HS256")
