# syntax=docker/dockerfile:1

# ---- builder -----------------------------------------------------------------
# Dependencies are built into a venv here so the runtime stage carries no
# compilers or pip cache.
FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copied on its own so dependency layers cache independently of source changes.
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# ---- runtime -----------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

RUN apt-get update \
    && apt-get install --no-install-recommends -y curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 prism

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY --chown=prism:prism prism_ch/ ./prism_ch/
COPY --chown=prism:prism sql/ ./sql/

USER prism
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS "http://localhost:${APP_PORT:-${PORT:-8000}}/health" || exit 1

ENTRYPOINT ["python", "-m", "prism_ch"]
CMD ["serve"]
