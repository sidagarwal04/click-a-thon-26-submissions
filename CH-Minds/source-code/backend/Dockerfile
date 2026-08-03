FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8001

# $PORT is set by Railway/Render at runtime; falls back to 8001 for local
# docker-compose, which doesn't set it. --reload dropped for a deployed
# target (dev convenience only, no reason to pay its overhead in prod).
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8001}"]
