FROM node:22-alpine AS frontend
WORKDIR /app/deploy/ui/frontend
COPY deploy/ui/frontend/package.json deploy/ui/frontend/package-lock.json ./
RUN npm ci
COPY deploy/ui/frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY deploy/ui/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY deploy/ui/backend ./backend
COPY deploy/ui/schema.sql ./schema.sql
COPY deploy/librechat/agents ./agents
COPY --from=frontend /app/deploy/ui/frontend/dist ./static
ENV AGENT_CONTEXT_DIR=/app/agents
EXPOSE 8090
CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8090"]
