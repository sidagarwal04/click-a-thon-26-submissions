# Deploy Atlys to VPS (gpthost.in)

Hackathon / short-lived demo deploy on a Linux VPS behind existing nginx + Let's Encrypt.
Domain: **https://gpthost.in** → nginx → `127.0.0.1:2283` → FastAPI (Docker).

Security is intentionally light; tear down after the event.

---

## Architecture

| Piece | Where |
|---|---|
| React UI + FastAPI API | Docker `fastapi` → host port **2283** |
| LibreChat (chat / LLM / MCP) | Docker `librechat` → host port **3080** (localhost only) |
| MongoDB | Docker `mongo` (bundled) |
| ClickHouse | ClickHouse Cloud (same service as local) |
| TLS / public entry | nginx on VPS for `gpthost.in` |

Users hit **https://gpthost.in** only. LibreChat UI is not public; the React app talks to it via FastAPI `POST /api/proxy/chat`.

---

## Prerequisites on the VPS

```bash
# Docker
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER   # re-login after

# Optional: only if you will load parquet on the VPS
sudo apt install -y git git-lfs   # or: sudo dnf install git git-lfs
git lfs install
```

Allowlist the **VPS public IP** in ClickHouse Cloud (or `0.0.0.0/0` for the demo day).

---

## 1. Bare git remote on the VPS

On the VPS:

```bash
mkdir -p ~/repos ~/clickathon2026
git init --bare ~/repos/clickathon2026.git

cat > ~/repos/clickathon2026.git/hooks/post-receive <<'EOF'
#!/bin/bash
git --work-tree="$HOME/clickathon2026" --git-dir="$HOME/repos/clickathon2026.git" checkout -f main
EOF
chmod +x ~/repos/clickathon2026.git/hooks/post-receive
```

Adjust paths if your bare repo lives elsewhere (e.g. `~/clickathon2026.git`).

---

## 2. Push from laptop

On the workstation (repo root):

```bash
git remote add ankk98-hzvps ankk98@ankk98-hzvps:repos/clickathon2026.git
# If bare repo path differs, match the VPS path, e.g.:
# git remote add ankk98-hzvps ankk98@ankk98-hzvps:clickathon2026.git
```

**Git LFS:** the VPS bare repo has no LFS transfer helper (`git-lfs-authenticate: command not found`). Skip LFS on this remote — parquet is not needed on the VPS if ClickHouse is already loaded:

```bash
GIT_LFS_SKIP_PUSH=1 git push -u ankk98-hzvps main
```

Later updates:

```bash
GIT_LFS_SKIP_PUSH=1 git push ankk98-hzvps
```

Optional — silence the locks warning:

```bash
git config lfs.https://ankk98-hzvps/clickathon2026.git/info/lfs.locksverify false
```

(Use the URL from `git remote get-url ankk98-hzvps` if it differs.)

---

## 3. Env file on the VPS

`.env` is not in git. Copy once:

```bash
# from laptop
scp Atlys/.env ankk98@ankk98-hzvps:~/clickathon2026/Atlys/.env
```

Required keys (see `Atlys/.env.example`):

| Var | Notes |
|---|---|
| `CH_HOST`, `CH_USER`, `CH_PASSWORD`, `CH_SECURE` | Same ClickHouse Cloud as local |
| `ZAI_API_KEY` | Required for chat |
| `CREDS_KEY` / `JWT_SECRET` / `JWT_REFRESH_SECRET` | `openssl rand -hex 32` each |
| `CREDS_IV` | `openssl rand -hex 16` |
| `LIBRECHAT_ADMIN_EMAIL` / `LIBRECHAT_ADMIN_PASSWORD` | Account you register once |
| `LANGFUSE_*` | Optional |

Leave `DOMAIN_CLIENT` / `DOMAIN_SERVER` as `http://localhost:3080`.

**Do not** copy a local `LIBRECHAT_API_KEY` into prod `.env` — it is tied to that LibreChat/Mongo instance and will 401 on a fresh VPS Mongo. Let `provision_agent.py` create a new key.

---

## 4. Map FastAPI to nginx port 2283

Existing nginx already proxies `gpthost.in` → `127.0.0.1:2283`. In `Atlys/docker-compose.yml` under `fastapi` → `ports`:

```yaml
ports:
  - "2283:8000"
```

Do not publish LibreChat publicly; keep `3080` bound for SSH tunnel / localhost only if needed.

---

## 5. Start the stack

```bash
cd ~/clickathon2026/Atlys
docker compose up -d --build
docker compose logs -f fastapi
```

Wait for uvicorn + agent provision (`Atlys PM`).

### One-time LibreChat admin register

Compose cannot create the first user. From the laptop:

```bash
ssh -L 3080:127.0.0.1:3080 ankk98@ankk98-hzvps
```

Open `http://localhost:3080`, register with the **exact** `LIBRECHAT_ADMIN_EMAIL` / `LIBRECHAT_ADMIN_PASSWORD` from `.env`, then:

```bash
docker compose restart fastapi
```

---

## 6. nginx

If FastAPI is on `2283`, **no nginx change**. Existing shape:

```nginx
# HTTP → HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name gpthost.in;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name gpthost.in;

    ssl_certificate /etc/letsencrypt/live/gpthost.in/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/gpthost.in/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    location / {
        proxy_pass http://127.0.0.1:2283;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Port $server_port;
        proxy_set_header X-Forwarded-Scheme $scheme;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header Host $host;
        proxy_request_buffering off;
        proxy_read_timeout 86400s;
        client_max_body_size 0;

        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
    }
}
```

Reload only if you edited it:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

---

## 7. Smoke test

```bash
curl -s https://gpthost.in/healthz
# → {"status":"ok",...}
```

Open **https://gpthost.in** and chat.

---

## Day-of update loop

```bash
# laptop
GIT_LFS_SKIP_PUSH=1 git push ankk98-hzvps

# VPS (post-receive already checks out; rebuild if Dockerfile / deps / UI changed)
cd ~/clickathon2026/Atlys
docker compose up -d --build
docker compose logs -f fastapi
```

Stop after the hackathon:

```bash
docker compose down          # keep Mongo volume
# docker compose down -v     # wipe Mongo too
```

---

## Troubleshooting

### `LibreChat proxy failed with status 401: Invalid API key`

Stale Agents API key. Provision **reuses** `LIBRECHAT_API_KEY` / `generated/.atlys_librechat_api_key` without validating; a fresh Mongo invalidates old keys.

```bash
cd ~/clickathon2026/Atlys
rm -f generated/.atlys_librechat_api_key generated/.atlys_agent_id
# remove LIBRECHAT_API_KEY=... from .env if set
docker compose restart fastapi
docker compose logs -f fastapi
```

Expect a **new** key create — not “Reusing existing LibreChat Agents API key”.

If 401 persists after a fresh key, check `ZAI_API_KEY` in `.env`.

### Git LFS push fails (`git-lfs-authenticate: command not found`)

Expected on this bare remote. Use `GIT_LFS_SKIP_PUSH=1`. Data load stays on ClickHouse Cloud / laptop.

### 502 from nginx

FastAPI not listening on 2283:

```bash
ss -tlnp | grep 2283
docker compose ps
docker compose logs fastapi
```

### LibreChat exits immediately

`CREDS_KEY` / `CREDS_IV` / `JWT_*` wrong length or not hex (`openssl rand -hex 32` / `16`).

### Chat tools / agent missing

Admin not registered, or restart `fastapi` after register so `provision_agent.py` runs.

### ClickHouse errors

VPS IP not allowlisted in ClickHouse Cloud.

---

## Related

- Full local / compose setup: [`Atlys/SETUP.md`](../Atlys/SETUP.md)
- Env template: [`Atlys/.env.example`](../Atlys/.env.example)
