FROM python:3.12-slim

RUN pip install --no-cache-dir clickhouse-connect==1.6.0 fastmcp==2.14.3 packaging
COPY server.py /app/server.py
USER 65532:65532
EXPOSE 8000
CMD ["python", "/app/server.py"]
