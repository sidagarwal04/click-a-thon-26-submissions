import os
import tempfile

import pytest


# Runs async tests (@pytest.mark.anyio) via asyncio. anyio's pytest plugin is already
# available transitively through FastAPI/Starlette — no new test dependency needed.
@pytest.fixture
def anyio_backend():
    return "asyncio"


# Tests must never depend on, or send data to, real external services — regardless of what
# the real .env has configured for local dev. Force these empty before any app module runs
# its import-time load_dotenv(), since dotenv only fills in keys that are ABSENT from
# os.environ, never ones already set (even to "").
for _key in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "GEMINI_API_KEY"):
    os.environ[_key] = ""

# Same reasoning for persisted reports: test_main.py's TestClient runs background tasks
# (including persist_report) synchronously, so without this a test run writes junk
# MagicMock-derived JSON straight into the real data/rca_reports/ the running agent serves.
os.environ["RCA_REPORTS_DIR"] = tempfile.mkdtemp(prefix="rca_reports_test_")
