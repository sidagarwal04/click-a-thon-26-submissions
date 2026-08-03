"""Make everything the browser journeys need, then say where it is.

Run before Playwright. Writes into `.e2e/`, which is disposable: a run that
cannot be reproduced from an empty directory is a run whose failures cannot be
trusted, so nothing here reads state it did not just create.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

from identity import ROLES, SigningKey, bind_identities, mint, write_jwks

_ROOT = Path(__file__).resolve().parents[2]
_OUTPUT = _ROOT / ".e2e"

OWNER_URL = os.environ.get(
    "DATABASE_OWNER_URL",
    "postgresql+psycopg://zentra_owner:zentra_owner@localhost:5432/zentra_control",
)


async def prepare(*, issuer: str) -> dict:
    key = SigningKey.generate()
    jwks_directory = _OUTPUT / "jwks"
    write_jwks(key, jwks_directory)
    await bind_identities(OWNER_URL)

    tokens = {role: mint(key, issuer=issuer, role=role) for role in ROLES}
    (_OUTPUT / "tokens.json").write_text(json.dumps(tokens, indent=2))
    return tokens


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--issuer", default="http://127.0.0.1:9099")
    args = parser.parse_args()

    _OUTPUT.mkdir(exist_ok=True)
    (_OUTPUT / ".gitignore").write_text("*\n")
    tokens = asyncio.run(prepare(issuer=args.issuer))

    print(f"JWKS      {_OUTPUT / 'jwks' / '.well-known' / 'jwks.json'}")
    print(f"tokens    {_OUTPUT / 'tokens.json'} ({', '.join(tokens)})")
    print(f"issuer    {args.issuer}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
