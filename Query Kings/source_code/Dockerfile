# Schema Kings — report UI + Ask API
# Job artifacts live in ClickHouse ops.job_artifacts (not baked into the image).
FROM node:22-bookworm-slim

RUN corepack enable && corepack prepare pnpm@10.32.1 --activate

WORKDIR /app

COPY backend/package.json backend/pnpm-lock.yaml backend/pnpm-workspace.yaml ./backend/
COPY backend/tsconfig.json ./backend/
RUN cd backend && pnpm install --frozen-lockfile

COPY backend/src ./backend/src
COPY specs ./specs
COPY base_context.md ./base_context.md
COPY infra ./infra
COPY frontend ./frontend
# Context bootstrap needs ddl.sql + instrumentation notes (parquet stays out via .dockerignore)
COPY data ./data

RUN mkdir -p frontend/dist

ENV NODE_ENV=production
ENV HOST=0.0.0.0
ENV PORT=8787

EXPOSE 8787

WORKDIR /app/backend
CMD ["pnpm", "cli", "serve"]
