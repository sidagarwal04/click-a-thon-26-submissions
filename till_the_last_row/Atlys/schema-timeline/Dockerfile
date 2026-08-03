# Schema-timeline web app — "Schema changes over time" (PROBLEM_STATEMENT.md §4).
# Standard-library only: a slim Python image + git is all it needs (no pip install,
# which also avoids the pypi TLS-inspection proxy issues seen elsewhere in this repo).
FROM python:3.13-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# The app reads the repo (git history + Atlys/schemas + context_docs/log.md) at
# runtime, so the repo is mounted at /repo. The app itself lives inside that mount,
# but we also copy it so the image is runnable standalone against a mounted repo.
WORKDIR /repo/Atlys/schema-timeline
COPY . /repo/Atlys/schema-timeline

# git refuses to operate on a repo owned by another uid (mounted volume); allow it.
RUN git config --global --add safe.directory /repo

ENV TIMELINE_HOST=0.0.0.0 \
    TIMELINE_PORT=8777

EXPOSE 8777
CMD ["python3", "server.py"]
