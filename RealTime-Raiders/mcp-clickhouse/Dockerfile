FROM python:3.12-slim

RUN pip install --no-cache-dir mcp-clickhouse

# /health returns 200 once the server can reach ClickHouse.
HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=12 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=4).status==200 else 1)"

CMD ["python", "-m", "mcp_clickhouse.main"]
