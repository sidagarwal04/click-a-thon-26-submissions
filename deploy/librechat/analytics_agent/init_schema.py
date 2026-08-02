#!/usr/bin/env python3
"""Deployment-time initialization for the append-only analytics artifact store."""

from pathlib import Path

from analytics_runner import create_client


def main() -> None:
    client = create_client()
    ddl = Path("/opt/atlys/ddl.sql").read_text(encoding="utf-8")
    for statement in (part.strip() for part in ddl.split(";")):
        if statement:
            client.command(statement)
    print("analytics artifact schema ready")


if __name__ == "__main__":
    main()
