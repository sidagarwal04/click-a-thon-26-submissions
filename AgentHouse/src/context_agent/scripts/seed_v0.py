#!/usr/bin/env python3
"""CLI: uv run python context_agent/scripts/seed_v0.py [--force]"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(_SRC))

from context_agent.seed_v0 import main

if __name__ == "__main__":
    main()
