FROM python:3.12-slim

WORKDIR /app

# Python block-buffers stdout when it is not a TTY, which in Docker means the scanner
# services produced NO log output at all until their buffer happened to fill -- verified:
# `docker compose logs scanner` was empty while the scanner was demonstrably sweeping
# (sweep_runs was growing in ClickHouse every 30s). A monitor whose logs are silent while
# it works is indistinguishable from one that has hung, and it also swallowed the startup
# line naming which dataset each scanner is monitoring.
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY engine/ engine/
COPY api/ api/
COPY Docs/metrics_glossary.md Docs/metrics_glossary.md
# The backtest record, served by GET /api/calibration and rendered at /method. Copied
# because it is a build artefact the running system reports about ITSELF -- without it
# the calibration page correctly says "this build has not been calibrated", which is
# honest but useless in the container that a judge actually opens. Regenerate with
# `python scripts/backtest.py` and rebuild; the file is small and version-controlled so
# the image always states the calibration of the code it was built from.
COPY Docs/backtest_scorecard.json Docs/backtest_scorecard.json

EXPOSE 8000

# Secrets/config come from the container environment (docker-compose's
# env_file), never baked into the image -- see PRODUCTION_PLAN.md's
# "config and secrets externalized" principle.
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
