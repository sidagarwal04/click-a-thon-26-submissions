# Railway deployment

Railway does not execute Docker Compose directly. Deploy this solution as one
Railway project containing the official Langfuse stack and the Prism app.

## 1. Deploy Langfuse

Deploy the official Langfuse v3 Railway template:

https://langfuse.com/self-hosting/deployment/railway

The template provisions Langfuse web and worker services plus PostgreSQL,
Redis, ClickHouse, and object storage. Keep the backing services private and
generate a public domain only for the Langfuse web service.

Generate production values for every Langfuse secret. Do not reuse the local
development values from `.env.example`. Create a Langfuse project and retain
its public and secret API keys for the Prism service.

## 2. Push Prism to Docker Hub

Choose a repository and authenticate using a Docker Hub access token:

```sh
docker login --username YOUR_DOCKERHUB_USER
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  --tag YOUR_DOCKERHUB_USER/atlys-prism-ch:latest \
  --tag YOUR_DOCKERHUB_USER/atlys-prism-ch:GIT_SHA \
  --push .
```

Use an immutable commit tag for Railway. `latest` is convenient for local use,
but it does not identify exactly what is running.

## 3. Create the Prism Railway service

In the same Railway project, create a service from the Docker Hub image. For a
private repository, configure registry credentials in the service settings.
Railway Pro is required for private registry images.

Copy `deploy/railway.env.example` into the service Variables editor and fill in
the values. Do not set `APP_PORT`; Railway injects `PORT` and the app binds to
it automatically. Generate a public domain for the Prism service.

Set `LANGFUSE_HOST` to the Langfuse web service's private Railway URL (typically
`http://langfuse-web.railway.internal:3000`) and use the matching project keys.
Set the ClickHouse variables to the analytics ClickHouse Cloud service used by
the agents, not Langfuse's internal ClickHouse database.

## 4. Verify

Check the Prism service deployment logs for both messages:

```text
connected to ClickHouse
tracing enabled
```

Then verify:

```sh
curl --fail https://YOUR_PRISM_DOMAIN/health
```

Run an agent action in the Prism UI and confirm its trace appears in Langfuse.
The backing database and object-storage services need persistent Railway
volumes; the official Langfuse template configures these.
