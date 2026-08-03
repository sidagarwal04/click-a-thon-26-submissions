"""Bootstrap Postgres metadata tables: ``uv run python -m instrumentation_agent.init_db``."""

from __future__ import annotations

from instrumentation_agent.db.connection import apply_meta_registry_ddl, ping


def main() -> None:
    print("Pinging Postgres…")
    ping()
    print("Applying meta registry DDL…")
    apply_meta_registry_ddl()
    print("Done.")


if __name__ == "__main__":
    main()
