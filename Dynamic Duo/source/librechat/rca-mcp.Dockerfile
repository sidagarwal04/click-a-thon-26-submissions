# rca-mcp sidecar: the custom MCP server (list_incidents / investigate /
# investigate_window) wired to the deterministic runner.
# Build context is the REPO ROOT (see docker-compose.yml) so the detector/, agent/,
# rca_mcp/ packages and sql/agent queries ship into the image unchanged.
FROM python:3.12-slim

WORKDIR /app
RUN pip install --no-cache-dir "mcp>=1.9,<2"

COPY detector/ detector/
COPY agent/ agent/
COPY rca_mcp/ rca_mcp/
COPY sql/ sql/

ENV PYTHONUNBUFFERED=1
EXPOSE 8100
CMD ["python", "-m", "rca_mcp.server"]
