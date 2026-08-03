"""Clickathon — automated root-cause analyst for InMobi ad metrics."""

__version__ = "0.1.0"


def main() -> None:
    from clickathon.cli import main as cli_main

    cli_main()
