# RCA backend — FastAPI + uvicorn. Runs from source (cwd on sys.path) so `import config`
# resolves /app/config.py and its sibling config.json, exactly like the local venv run.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Dependencies first for layer caching. Mirrors backend/pyproject.toml [project.dependencies].
# langfuse>=3: the tracing code uses the v3/v4 SDK (propagate_attributes, start_as_current_
# observation). The host venv runs 4.x; an older SDK ImportErrors and 500s /investigate.
RUN pip install --no-cache-dir \
    "clickhouse-connect>=0.7" \
    "fastapi>=0.110" \
    "uvicorn[standard]>=0.29" \
    "pydantic>=2.6" \
    "python-dotenv>=1.0" \
    "pandas>=2.2" \
    "scikit-learn>=1.4" \
    "langfuse>=3" \
    "jsonschema>=4.21" \
    "boto3>=1.34"

COPY . .

EXPOSE 8000

# 0.0.0.0 so the published port is reachable from the host / other containers.
CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
