#!/usr/bin/env python3
"""CLI wrapper: uv run python context_agent/scripts/init_schema.py"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(_SRC))

from context_agent.init_schema import main

if __name__ == "__main__":
    main()
