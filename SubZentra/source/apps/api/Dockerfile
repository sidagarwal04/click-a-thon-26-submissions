FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /workspace

COPY pyproject.toml uv.lock ./
COPY apps/api apps/api
COPY libs/adapters libs/adapters
COPY libs/domain libs/domain

RUN uv sync --frozen --no-dev

EXPOSE 8000

CMD ["sh", "-c", "uv run alembic -c libs/adapters/postgres/alembic.ini upgrade head && uv run uvicorn zentra_api.main:app --app-dir apps/api/src --host 0.0.0.0 --port 8000"]
