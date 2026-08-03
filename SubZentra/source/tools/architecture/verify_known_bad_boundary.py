from __future__ import annotations

import ast
from pathlib import Path

FORBIDDEN_ROOTS = {
    "alembic",
    "anthropic",
    "clickhouse_connect",
    "fastapi",
    "langchain_core",
    "langgraph",
    "openai",
    "httpx",
    "opentelemetry",
    "psycopg",
    "sqlalchemy",
    "uvicorn",
}


def forbidden_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name.split(".", maxsplit=1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module.split(".", maxsplit=1)[0])
    return found & FORBIDDEN_ROOTS


FIXTURES = {
    "libs/domain/agent-execution/tests/architecture_fixture/invalid_domain.py": {"fastapi"},
    "libs/domain/agent-execution/tests/architecture_fixture/invalid_agent_domain.py": {
        "anthropic",
        "langgraph",
    "openai",
    },
}


if __name__ == "__main__":
    for path, expected in FIXTURES.items():
        violations = forbidden_imports(Path(path))
        if violations != expected:
            raise SystemExit(
                f"{path} did not produce the expected violation: {violations} (expected {expected})"
            )
        print(f"Known-bad boundary fixture correctly rejected: {sorted(expected)}")
