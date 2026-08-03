import os
from urllib.parse import urlparse

CLICKHOUSE_HTTP_URL = os.environ.get("CLICKHOUSE_HTTP_URL", "http://clickhouse:8123")
_parsed = urlparse(CLICKHOUSE_HTTP_URL)
CLICKHOUSE_HOST = _parsed.hostname or "clickhouse"
CLICKHOUSE_PORT = _parsed.port or 8123
# ClickHouse Cloud terminates TLS on 8443/https; local Docker is plain http on 8123.
CLICKHOUSE_SECURE = _parsed.scheme == "https"
CLICKHOUSE_DATABASE = "inmobi_rca"

CLICKHOUSE_READONLY_USER = os.environ["CLICKHOUSE_READONLY_USER"]
CLICKHOUSE_READONLY_PASSWORD = os.environ["CLICKHOUSE_READONLY_PASSWORD"]

# Admin creds: only for backend-authored inserts, never exposed to LLM code.
CLICKHOUSE_ADMIN_USER = os.environ["CLICKHOUSE_ADMIN_USER"]
CLICKHOUSE_ADMIN_PASSWORD = os.environ["CLICKHOUSE_ADMIN_PASSWORD"]

ACTIVE_LLM_PROVIDER = os.environ.get("ACTIVE_LLM_PROVIDER", "openai").lower()
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")

LANGFUSE_PUBLIC_KEY = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY = os.environ.get("LANGFUSE_SECRET_KEY", "")
LANGFUSE_HOST = os.environ.get("LANGFUSE_HOST", "http://langfuse-web:3000")
LANGFUSE_WEB_PUBLIC_URL = os.environ.get("LANGFUSE_WEB_PUBLIC_URL", "http://localhost:3000")

MIN_VOLUME_FLOOR = int(os.environ.get("MIN_VOLUME_FLOOR", "1000"))
PCT_DEVIATION_THRESHOLD = float(os.environ.get("PCT_DEVIATION_THRESHOLD", "0.30"))
Z_SCORE_THRESHOLD = float(os.environ.get("Z_SCORE_THRESHOLD", "2.5"))
TRAILING_WEEKS = int(os.environ.get("TRAILING_WEEKS", "4"))

# Static fallback for thresholds.py when there isn't enough history yet to
# trust a computed percentile (cold start on new/small data).
MIN_THRESHOLD_SAMPLES = int(os.environ.get("MIN_THRESHOLD_SAMPLES", "30"))
MIN_PCT_DEVIATION_THRESHOLD = float(os.environ.get("MIN_PCT_DEVIATION_THRESHOLD", "0.05"))
MIN_VOLUME_FLOOR_ABSOLUTE = int(os.environ.get("MIN_VOLUME_FLOOR_ABSOLUTE", "200"))

# Below this many prior same-weekday observations, a deviation isn't treated
# as evidence - see scan()'s coverage block for the "not evaluated" state.
MIN_BASELINE_SAMPLES = int(os.environ.get("MIN_BASELINE_SAMPLES", "2"))
