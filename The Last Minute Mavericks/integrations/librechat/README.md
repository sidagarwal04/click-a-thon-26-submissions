# LibreChat for RootCauseOS

LibreChat is the chat front-end for the RCA agent. It talks to the
OpenAI-compatible shim (`integrations/openai_shim.py`) on host port 8601.

## Start

1. Start the shim on the host: `python integrations/openai_shim.py`
2. Start LibreChat from this directory: `docker compose up -d`

## First run

1. Open http://localhost:3080 in a browser.
2. Click "Sign up" and register a local account.
3. Log in. Select the "RootCauseOS RCA" model and ask a question.

## Endpoint configuration

The file `librechat.yaml` in this directory defines the custom endpoint.
It points at `http://host.docker.internal:8601/v1` (the shim on the host)
and exposes one model: `rootcauseos-rca`. Secrets live in `.env`
(gitignored). Copy `.env.example` to `.env` and fill in real values.

## Dashboard dock

The Streamlit dashboard (`ui/app.py`) embeds LibreChat in an iframe.
Set `LIBRECHAT_URL` to change the target (default: http://localhost:3080).

## Verify the shim from the container

The LibreChat container image does not ship `curl`, so use the Node
runtime that is already inside it to fetch the shim's model list:

    docker exec rcos-librechat node -e \
      "fetch('http://host.docker.internal:8601/v1/models').then(r=>r.json()).then(d=>console.log(d.data.map(m=>m.id)))"

The output must list the model `rootcauseos-rca`.
