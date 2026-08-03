# Base on the mcp-clickhouse image because it already ships Python 3.13 + a working
# fastmcp install in /app/.venv. This avoids a `pip install` at build time, which fails
# on this network (pypi.org TLS is intercepted by a proxy the container can't verify).
FROM ghcr.io/clickhouse/mcp-clickhouse:latest

USER root

# git is available from Debian repos (not behind the pypi TLS-inspection proxy).
RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY server.py /app/git_server.py

RUN mkdir -p /work
ENV CH_REPO_DIR=/work/repo \
    MCP_BIND_HOST=0.0.0.0 \
    MCP_BIND_PORT=8000

EXPOSE 8000
# Use the image's venv python (has fastmcp). Override the base image's entrypoint/cmd.
ENTRYPOINT []
CMD ["/app/.venv/bin/python", "/app/git_server.py"]
