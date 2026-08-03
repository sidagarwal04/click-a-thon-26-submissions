from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

import jwt
from jwt import PyJWKClient

logger = logging.getLogger(__name__)


class AuthenticationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ClerkPrincipal:
    subject_id: str
    organization_id: str


class ClerkJwtVerifier:
    def __init__(self, issuer: str | None, audience: str | None) -> None:
        self._issuer = issuer.rstrip("/") if issuer else None
        # `or None` matters: CLERK_AUDIENCE= in a .env file parses as "", and an
        # empty string is not None, so audience verification would switch on and
        # reject every token for missing a claim it was never meant to carry.
        # Configured-but-blank means unconfigured.
        self._audience = audience or None
        self._jwks = (
            PyJWKClient(f"{self._issuer}/.well-known/jwks.json")
            if self._issuer
            else None
        )

    async def verify(self, token: str) -> ClerkPrincipal:
        if not self._issuer or not self._jwks:
            raise AuthenticationError("Clerk issuer is not configured")
        try:
            key = await asyncio.to_thread(self._jwks.get_signing_key_from_jwt, token)
            options = {"verify_aud": self._audience is not None}
            claims: dict[str, Any] = jwt.decode(
                token,
                key.key,
                algorithms=["RS256"],
                audience=self._audience,
                issuer=self._issuer,
                options=options,
            )
        except jwt.PyJWTError as error:
            # The client is told nothing beyond "invalid" — a verifier that
            # explains why is a verifier that helps forge. The operator gets the
            # reason, because "Invalid bearer token" alone cannot distinguish a
            # wrong issuer from an expired token from a key rotation.
            logger.warning(
                "Rejected bearer token: %s: %s",
                type(error).__name__,
                error,
            )
            raise AuthenticationError("Invalid bearer token") from error

        subject_id = claims.get("sub")
        organization_id = claims.get("org_id")
        if not organization_id and isinstance(claims.get("o"), dict):
            organization_id = claims["o"].get("id")
        if not isinstance(subject_id, str) or not subject_id:
            raise AuthenticationError("Token is missing its subject")
        if not isinstance(organization_id, str) or not organization_id:
            raise AuthenticationError("An active Clerk organization is required")
        return ClerkPrincipal(
            subject_id=subject_id,
            organization_id=organization_id,
        )


def bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise AuthenticationError("Bearer token is required")
    scheme, separator, value = authorization.partition(" ")
    if separator != " " or scheme.lower() != "bearer" or not value:
        raise AuthenticationError("Authorization must use the Bearer scheme")
    return value
