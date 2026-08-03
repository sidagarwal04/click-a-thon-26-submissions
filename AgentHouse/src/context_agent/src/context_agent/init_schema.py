"""Apply postgres_catalog.sql using a writable DATABASE_URL connection."""

from __future__ import annotations

from importlib import resources
from pathlib import Path

from sqlalchemy import text

from context_agent.db import get_writable_engine


def _load_sql() -> str:
    here = Path(__file__).resolve().parent
    # Repo: context_agent/src/context_agent/init_schema.py → ../../sql/ (parents[1]=context_agent)
    # Packaged: .../site-packages/context_agent/init_schema.py → ./sql/
    candidates = [
        here.parents[1] / "sql" / "postgres_catalog.sql",
        here / "sql" / "postgres_catalog.sql",
        Path.cwd() / "context_agent" / "sql" / "postgres_catalog.sql",
    ]
    for path in candidates:
        if path.is_file():
            return path.read_text(encoding="utf-8")
    try:
        return (
            resources.files("context_agent")
            .joinpath("sql/postgres_catalog.sql")
            .read_text(encoding="utf-8")
        )
    except (FileNotFoundError, TypeError, AttributeError, ModuleNotFoundError):
        pass
    raise FileNotFoundError(
        "postgres_catalog.sql not found. Expected at context_agent/sql/postgres_catalog.sql "
        f"(tried: {', '.join(str(c) for c in candidates)})"
    )


def apply_schema() -> None:
    sql = _load_sql()
    engine = get_writable_engine()
    with engine.begin() as conn:
        for raw in sql.split(";"):
            lines = [
                ln
                for ln in raw.splitlines()
                if ln.strip() and not ln.strip().startswith("--")
            ]
            if not lines:
                continue
            conn.execute(text("\n".join(lines)))


def main() -> None:
    apply_schema()
    print("Applied context_agent postgres catalog schema.")


if __name__ == "__main__":
    main()
