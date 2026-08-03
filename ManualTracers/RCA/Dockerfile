# Build context is the repo root (see docker-compose.yml), not RCA/ — pyproject.toml and
# uv.lock live at the root, and RCA/app imports as the `app` package relative to RCA/, so
# both have to be reachable in the same COPY tree.
FROM python:3.13-slim
WORKDIR /repo

# Corporate networks often MITM PyPI with a private CA; match rca-api/rca-ui npm workaround.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv \
         --trusted-host pypi.org \
         --trusted-host files.pythonhosted.org

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev \
    --allow-insecure-host pypi.org \
    --allow-insecure-host files.pythonhosted.org

COPY RCA ./RCA

WORKDIR /repo/RCA
EXPOSE 8000
CMD ["/repo/.venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
