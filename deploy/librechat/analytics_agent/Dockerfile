FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir \
    clickhouse-connect \
    fastmcp==2.14.3 \
    pandas \
    scipy \
    statsmodels

WORKDIR /opt/atlys
COPY analytics_runner.py server.py init_schema.py ddl.sql /opt/atlys/

USER 65532:65532
EXPOSE 8000
CMD ["python", "/opt/atlys/server.py"]
