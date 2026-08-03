"""CLI: clickathon investigate|scan|mcp|detect|materialize."""

from __future__ import annotations

import json
from typing import Optional

import typer
from rich.console import Console

app = typer.Typer(help="Clickathon RCA engine")
console = Console()


@app.command()
def investigate(
    day: str = typer.Argument(..., help="YYYY-MM-DD"),
    no_narrative: bool = typer.Option(False, help="Skip LLM narration"),
    pretty: bool = typer.Option(True, help="Pretty-print JSON"),
) -> None:
    """Run full RCA for a day."""
    from clickathon.investigate import investigate as run

    findings = run(day, narrate=not no_narrative)
    text = json.dumps(findings, default=str, indent=2 if pretty else None)
    # Avoid Windows cp1252 crashes on unicode from LLM/JSON
    try:
        console.print(text)
    except UnicodeEncodeError:
        print(text.encode("utf-8", errors="replace").decode("utf-8"))
    if pretty and findings.get("narrative"):
        console.print("\n[bold]Narrative[/bold]\n")
        console.print(findings["narrative"])


@app.command("scan")
def scan_cmd(
    start: Optional[str] = typer.Argument(None, help="Start YYYY-MM-DD (raw day flags)"),
    end: Optional[str] = typer.Argument(None, help="End YYYY-MM-DD (raw day flags)"),
    raw: bool = typer.Option(
        False,
        "--raw",
        help="Day-level wow flags (includes recoveries) instead of the four EDA incidents",
    ),
) -> None:
    """List discovered incidents (default), or raw day-level wow with --raw."""
    if raw or start or end:
        from clickathon.investigate import scan_anomalies

        console.print_json(data=scan_anomalies(start, end))
    else:
        from clickathon.rca_store import list_incidents_from_store

        try:
            data = list_incidents_from_store()
            if data.get("count", 0) == 0:
                from clickathon.incidents import discover_incidents

                data = discover_incidents()
        except Exception:
            from clickathon.incidents import discover_incidents

            data = discover_incidents()
        console.print_json(data=data)

@app.command()
def detect(day: str = typer.Argument(...)) -> None:
    """Same-DOW wow for one day."""
    from clickathon.detect import daily_wow

    console.print_json(data=daily_wow(day))


@app.command()
def mcp(
    host: str = typer.Option("0.0.0.0", help="Bind host"),
    port: int = typer.Option(8001, help="Bind port"),
) -> None:
    """Run RCA MCP server (streamable HTTP) for LibreChat."""
    from clickathon.mcp_server import main as run_mcp

    run_mcp(host=host, port=port)


@app.command()
def materialize(
    rollup: bool = typer.Option(
        False,
        "--rollup",
        help="Rebuild metrics_hourly from ad_events before RCA layers",
    ),
    check: bool = typer.Option(
        False,
        "--check",
        help="Only validate rca_* tables (no rebuild)",
    ),
    calibration: bool = typer.Option(
        False,
        "--calibration",
        help="With --check, assert the 4 known windows on the current synthetic dataset",
    ),
) -> None:
    """Batch-build ClickHouse rca_* tables (functions + INSERT…SELECT + incident assemble)."""
    from clickathon.materialize import check_materialize, materialize as run_mat

    if check:
        console.print_json(data=check_materialize(calibration=calibration))
        return
    result = run_mat(rollup=rollup)
    console.print_json(data=result)
    chk = check_materialize(calibration=calibration)
    console.print_json(data=chk)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
