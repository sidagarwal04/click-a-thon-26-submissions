FROM python:3.12-slim
WORKDIR /app

# curl is used by run_pipeline.sh to check the agent is up before seeding
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
CMD ["bash", "scripts/run_pipeline.sh"]