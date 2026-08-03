# One image, two services (see ../docker-compose.yml): rca-dashboard runs
# `rca serve`, rca-mcp runs `rca mcp-serve`. Same package, different CMD.
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY rca ./rca
COPY sql ./sql

RUN pip install --no-cache-dir -e .

# out/ and traces/ are written relative to the cwd (WORKDIR) at runtime --
# see rca/tracing.py and rca/cli.py -- and are bind-mounted from the host in
# docker-compose.yml so investigation results and traces survive a restart
# and stay inspectable from outside the container.
RUN mkdir -p out traces

EXPOSE 8000 8001

CMD ["rca", "serve", "--host", "0.0.0.0"]
