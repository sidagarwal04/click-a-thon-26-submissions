## How to run it

1. **Install Python dependenciess**: `pip install -r requirements.txt`

2. **Copy `.env.example` to `.env`** and fill in:
   - `CLICKHOUSE_HOST`: "fhrv7n6gue.ap-south-1.aws.clickhouse.cloud"
   - `CLICKHOUSE_USER`: "default"
   - `CLICKHOUSE_PASSWORD`: "Mt5Cbu.xHVrMK"
   - `ANTHROPIC_API_KEY` (preferred LLM provider — see `agents/config.py:AnthropicConfig`, default model `claude-haiku-4-5-20251001`) or `OPENROUTER_API_KEY` (fallback if Anthropic isn't set).
   - `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` (optional, for tracing)

3. **Run the pipeline**:

   ```bash
   python main.py specs/06_checkout_promo/
   ```

   This runs Context → Instrumentation → Analytics → Visualization end to end and writes, into the spec directory:
   - `generated_schema.sql` — the DDL record (tables + materialized view)
   - `insight_summary.md` — the Analytics Agent's markdown insights