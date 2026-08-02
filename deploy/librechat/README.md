# LibreChat VM Deployment

This directory provides a production baseline for a single VM running LibreChat's official `deploy-compose.yml` stack. It retains the requested remote-agent API permissions (`use` and `create`) and makes agent builder, chaining, subagents, tools, code execution, and context available.

## One-time VM preparation

1. Install Docker Engine with the Compose plugin, Git, OpenSSH server, and rsync.
2. Create a non-root deployment user that is in the `docker` group. Restrict SSH to key authentication and allow only the ports required by the TLS reverse proxy.
3. Clone the reviewed LibreChat release into `/opt/LibreChat`, then upload `.env.production.example` from this directory as `/opt/LibreChat/.env`.
4. Replace every placeholder secret in `.env` using `openssl rand -hex 32` (use `openssl rand -hex 16` for `CREDS_IV`), set the real HTTPS domains, and run `chmod 600 /opt/LibreChat/.env`.
5. Install the host Nginx site from `nginx/clickathon26librechat.nannan.in.conf`, then issue the public certificate and HTTPS redirect:
   `sudo certbot --nginx -d clickathon26librechat.nannan.in --non-interactive --agree-tos -m meow@nannan.in --redirect`
   Ensure the VM/network security group allows inbound TCP ports 80 and 443 for ACME validation and public HTTPS.

## Agent chain

See [AGENT_CHAIN.md](AGENT_CHAIN.md) for the sequential subagent workflow,
handoff payload contract, storage behavior, and deployment requirements.
5. Put a TLS-terminating reverse proxy in front of LibreChat. Route `chat.example.com` to the application and `admin.chat.example.com` to the admin panel. Do not expose MongoDB, Meilisearch, PostgreSQL, RAG, or the API container ports to the internet. The production Compose override binds the bundled LibreChat frontend only to `127.0.0.1:8080` for this purpose.

Create the first administrator before setting `ALLOW_REGISTRATION=false`. Keep the remote-agent permission settings in YAML as requested, then use LibreChat's Admin Panel to limit `REMOTE_AGENTS` permissions to the intended roles.

## Deploy over SSH

From the repository root, run:

```bash
./deploy/librechat/deploy.sh
```

Set these local-only values in `deploy/librechat/.env` (do not commit them):

```dotenv
SSH_TARGET=deployer@vm.example.com
SSH_PASSWORD=your-ssh-password
LIBRECHAT_REF=vX.Y.Z
AGENT_MODEL=gpt-5.6-luna
OPENAI_API_KEY=your-openai-api-key
```

`LIBRECHAT_REF` is intentionally required and rejects moving branches/tags. Review and pin it to the LibreChat release or commit you intend to operate. The script reads only its named deployment variables from `.env`; it does not source the file. It verifies that the VM's secret `.env` already exists, uploads the LibreChat configuration, production Compose override, and `agents/` context files, validates the merged Compose configuration, pulls images, and starts the official deployment stack. The override keeps the API on Docker's internal network instead of publishing port `3080` on the VM.

The remote-agent API is enabled by `interface.remoteAgents`. It is authenticated by LibreChat API keys by default; treat those keys as production credentials and rotate/revoke them through LibreChat when necessary. For machine-to-machine access, configure OIDC in `endpoints.agents.remoteApi.auth` before disabling API-key authentication.

## Operations

Before upgrades, back up `/opt/LibreChat/data-node`, `/opt/LibreChat/meili_data_v1.35.1`, `/opt/LibreChat/uploads`, `/opt/LibreChat/images`, and the Docker volume that stores PostgreSQL data. Check `docker compose -f deploy-compose.yml logs --tail=200 api` after each deployment and keep host OS/Docker security updates on a regular schedule.
