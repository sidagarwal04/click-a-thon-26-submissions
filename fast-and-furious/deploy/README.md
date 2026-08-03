# Deploying to EC2

`deploy.sh` builds the Go binaries locally, ships them over SSH, installs them
atomically, and restarts the service. It does **not** provision the box — that is
a one-time root task, listed below, kept manual because it touches credentials
and a systemd unit and should be auditable rather than a side effect of shipping.

```bash
DEPLOY_HOST=ec2-1-2-3-4.eu-west-1.compute.amazonaws.com ./deploy/deploy.sh
```

`./deploy/deploy.sh --help` lists every flag and variable.

There are four deploy scripts, one per thing that ships on its own schedule:

| Script | Ships | Notes |
|---|---|---|
| `deploy.sh` | `sonyliv-api`, `sonyliv-mock`, the CLIs | Go binaries, systemd |
| `deploy-mcp.sh` | `sonyliv-mcp` | Go binary, systemd, restricted CH user |
| `deploy-librechat.sh` | LibreChat + LiteLLM | Docker Compose, prompt from Langfuse |
| — | nginx | `nginx/sonyliv.conf`, copied by hand once |

---

## One-time box setup

Everything here runs as root on the EC2 instance, once.

**1. Service account.** Unprivileged, no home, no shell.

```bash
sudo useradd --system --no-create-home --shell /usr/sbin/nologin sonyliv
```

**2. ClickHouse credentials.** `deploy.sh` never writes this file, so your
ClickHouse password never travels through the deploy path.

```bash
sudo mkdir -p /etc/sonyliv
sudo tee /etc/sonyliv/sonyliv.env >/dev/null <<'EOF'
CLICKHOUSE_HOST=your-service.aws.clickhouse.cloud
CLICKHOUSE_PORT=9440
CLICKHOUSE_USER=claude
CLICKHOUSE_PASSWORD=...
CLICKHOUSE_DATABASE=default
CLICKHOUSE_SECURE=true
EOF
sudo chown root:sonyliv /etc/sonyliv/sonyliv.env
sudo chmod 0640 /etc/sonyliv/sonyliv.env
```

Same variable names `ingest/internal/config` already reads, so the CLI and the
API pick them up with no extra wiring. `0640` root:sonyliv — readable by the
service, not by other users on the box.

**3. Sudo for the deploy user.** `deploy.sh` needs root to write `/usr/local/bin`
and restart the unit. Scope it to exactly that rather than granting blanket sudo:

```bash
echo 'ec2-user ALL=(root) NOPASSWD: /bin/bash' | sudo tee /etc/sudoers.d/sonyliv-deploy
sudo chmod 0440 /etc/sudoers.d/sonyliv-deploy
```

The remote half of the deploy is a single `sudo bash -s` invocation, which is why
this is `/bin/bash` rather than a list of commands. That is broad — if you want it
tighter, replace the remote block with a fixed script installed on the box and
grant NOPASSWD on that path alone.

**4. The unit** (only once `sonyliv-api` exists — until then `deploy.sh` detects
the missing unit and skips the restart):

```bash
sudo cp deploy/sonyliv-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable sonyliv-api
```

**5. Security group.** The API port should not be reachable from `0.0.0.0/0`. The
deploy's health check runs *on the box* against `127.0.0.1` precisely so shipping
never depends on the port being publicly open.

---

## SSH key

RSA, as chosen. Generate at a modern size:

```bash
ssh-keygen -t rsa -b 4096 -f ~/.ssh/sonyliv_deploy
ssh-copy-id -i ~/.ssh/sonyliv_deploy.pub ec2-user@HOST
chmod 600 ~/.ssh/sonyliv_deploy
DEPLOY_KEY=~/.ssh/sonyliv_deploy ./deploy/deploy.sh
```

Two things that produce a misleading `Permission denied (publickey)`:

- **Key permissions.** ssh refuses a group- or world-readable private key.
  `deploy.sh` checks this in preflight and tells you to `chmod 600`.
- **A genuinely old RSA key.** OpenSSH ≥ 8.8 disables the legacy `ssh-rsa`
  *signature algorithm* by default. Keys generated in the last few years work
  fine over `rsa-sha2-256/512`; only an ancient key fails, and it fails looking
  exactly like a wrong key. Diagnose with `ssh -v`.

Password authentication is not supported here, and would not work on a stock EC2
AMI anyway — the standard AMIs ship `PasswordAuthentication no`.

---

## What a deploy does

1. **Preflight** — `go` present, key readable and `0600`, host reachable. Fails
   before spending time on a build.
2. **`make check`** — tests, `go vet`, `gofmt`. `--skip-checks` to bypass.
3. **Cross-compile** `linux/amd64`, `CGO_ENABLED=0`, `-trimpath`. Every directory
   under `ingest/cmd/` is built, discovered rather than hardcoded, so a new binary
   ships with no change to the script.
4. **Ship and verify** — `scp` to `/tmp/sonyliv-deploy-<version>.<pid>/`, then
   compare `sha256sum` both sides. A truncated transfer is caught before it
   becomes a broken binary.
5. **Install atomically** — a running binary cannot be overwritten in place
   (`ETXTBSY`), so the new one is written alongside and `mv`'d over. `mv` within
   one filesystem is atomic, so the path is never missing or half-written. The
   previous binary is kept as `<name>.prev`.
6. **Restart** — only if the unit is installed. `daemon-reload`, `restart`, then
   require `is-active` to hold.
7. **Health check, then roll back on failure** — polls `DEPLOY_HEALTH_URL` from on
   the box for 30s. If the service will not come up, `.prev` binaries are restored
   and the unit restarted, and the script exits `4`. A deploy that leaves the
   service down is worse than one that refuses.

Exit codes: `0` ok, `1` usage/preflight, `2` build failed, `3` transfer or verify
failed, `4` service did not come up (rolled back).

What is running:

```bash
ssh ec2-user@HOST cat /usr/local/bin/.sonyliv-deployed-version
```

---

## The chat surface: LibreChat, Langfuse and the serving layer

An analyst sits in front of the concurrency serving layer and answers viewing-trend
questions from it. Three pieces, each doing one job:

```
browser ──TLS─→ nginx :443  ──→ LibreChat        127.0.0.1:3080   (docker)
        ──TLS─→ nginx :8443 ──→ sonyliv-mock     127.0.0.1:8081   (systemd)

LibreChat ──OpenAI-compatible──→ LiteLLM (docker) ──→ Gemini
                                    └── success_callback: langfuse ──→ Langfuse Cloud
LibreChat ──MCP streamable-http──→ sonyliv-mcp   172.17.0.1:8848  (systemd)
                                    └──→ ClickHouse Cloud as sonyliv_mcp
```

**What traces what.** Both halves report to Langfuse Cloud, and they are complementary
rather than redundant — measured, not assumed:

| Source | Trace | Carries |
|---|---|---|
| LibreChat (native, v0.8.7) | `AgentRun`, tagged `librechat` | the LangGraph structure and a **TOOL span per MCP call** with its arguments and output |
| LiteLLM sidecar | `litellm-acompletion` | **token counts and cost** per model call, which the LibreChat spans do not carry |

So LiteLLM is not there to make tracing possible — LibreChat's own instrumentation
picks up `LANGFUSE_*` from the environment and does the interesting half. It is there
for the cost and token accounting, and it is one container to get it. If two traces per
turn is noise for your demo, drop `success_callback` from `litellm-config.yaml` and
keep LibreChat's.

Verified in the generation input of a real trace: the analyst prompt, its Langfuse
version stamp, **and** the MCP server's injected rules all reach the model.

**Where the prompt lives.** `librechat/prompts/serving-analyst.md` is the *authored*
source: what review reads, what git records. Langfuse prompt management is the
*runtime* source of truth: what the deployed agent loads, and what records who changed
it. `langfuse-prompt-sync.sh` renders the `production`-labelled version into
`librechat.yaml` at deploy time, and **fails closed** — a Langfuse outage leaves the
previous file in place and stops the deploy, because an analyst without the additivity
and grouping rules confidently reports a nine-fold overcount.

Langfuse links a trace to a prompt version only when its SDK is handed the prompt
object, and LibreChat → LiteLLM has no channel to carry one. The sync stamps
`<!-- langfuse:<name> v<N> -->` as the first line of the system prompt instead, so the
version is visible in the trace input. That is a substitute for the linkage, not the
linkage itself.

**How the model learns the schema.** It is not pasted into the prompt.
`serverInstructions: true` on the MCP server injects the rules the server returns from
`initialize` — never sum a peak, always pin the grouping, a missing minute is not an
empty one — into the system message alongside the tools. They therefore stay in step
with the server rather than being a copy that drifts, and they reach the model even in
a conversation that started before anyone read the prompt.

### One-time box setup

**0. The restricted ClickHouse user, first.** Nothing below works without it, and it
needs an admin — `sonyliv_svc` holds no `ACCESS MANAGEMENT` (verified: it cannot even
`SELECT` from `system.users`). ClickHouse Cloud has no SQL-over-API endpoint, so the
admin path is the console, or resetting `default` through the Cloud API:

```bash
PATCH /v1/organizations/{orgId}/services/{serviceId}/password
     {"newPasswordHash": "<base64 sha256>", "newDoubleSha1Hash": "<hex double sha1>"}
```

Cloud enforces a password policy the SQL file's placeholder does not hint at: at least
one uppercase character and one special character. A hex password is rejected with
`BAD_ARGUMENTS`, which reads like a syntax error in the DDL rather than a policy.

Then run `ingest/sql/009_mcp_reader.sql` with the placeholder substituted — one
statement per request over the HTTP interface, since it runs one query per call — and
prove it:

```bash
MCP_CH_PASSWORD=… ./ingest/cmd/sonyliv-mcp/check-grants.sh   # 37 passed, 0 failed
```

That run is the only thing that tests the grant boundary; the guard alone can be tested
with `--dev-unrestricted`, which bypasses the preflight but proves nothing about grants.

One thing it taught us. `system.tables` and `system.columns` are readable by
`sonyliv_mcp` and **cannot be revoked** — ClickHouse always exposes them, filtered to
the objects the caller is granted. There is no grant to take away; the filtering *is*
the mechanism. So the check no longer asserts they refuse. It asserts what actually
matters: that they reveal nothing outside the serving layer. Measured, they return
exactly the 8 granted objects and one database.

**1. Bind the MCP server where a container can reach it.** A container cannot reach the
host's `127.0.0.1`. Add to `/etc/sonyliv/mcp.env`:

```bash
MCP_ADDR=172.17.0.1:8848      # confirm: ip -4 addr show docker0
```

Then `MCP_HOST=… ./deploy/deploy-mcp.sh`. The Docker bridge is host-local, so this is
not a loosening — nothing plaintext leaves the box and 8848 is not in the security
group. The unit now orders itself `After=docker.service`, since the address does not
exist until dockerd has created `docker0`.

**2. Docker.** The box is Ubuntu 26.04 (`ubuntu@172.30.105.171`, ssh alias `sonyliv`),
8 vCPU / 15.7 GB, on a private network with **no public IPv4** — reachable only from
inside the VPC.

```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-v2 nginx jq rsync
sudo systemctl enable --now docker
sudo usermod -aG docker ubuntu       # log out and back in
```

**3. Secrets**, root-owned `0600`, same convention as `sonyliv.env`. Template and
generation commands are in `librechat/.env.example`:

```bash
sudo install -m 600 -o root -g root /dev/null /etc/sonyliv/librechat.env
sudo vi /etc/sonyliv/librechat.env
```

`SONYLIV_MCP_TOKEN` must equal the one in `mcp.env`. If they drift, every tool call
returns 401 and the model reports that it *has no data* rather than that it is
unauthorised — a confusing failure worth ruling out first.

**4. nginx, and move the dashboard to 8443.** LibreChat has no base-path support, so it
takes the root of `:443` and the dashboard moves to its own port. In
`/etc/sonyliv/sonyliv.env`:

```bash
MOCK_LISTEN=127.0.0.1:8081
MOCK_TLS_ARGS=
```

Then:

```bash
sudo cp deploy/nginx/sonyliv.conf /etc/nginx/conf.d/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl restart nginx     # restart, not reload: nginx was
sudo systemctl restart sonyliv-mock               # started by apt before this file existed
```

The cert is the pair the mock already served itself with,
`/etc/sonyliv/tls/server.{crt,key}` — one self-signed cert, now on both ports.

No security-group change was needed: the box has no public IP, so both listeners are
already confined to the VPC. Reverting is those two env lines plus a restart.

**5. Seed the prompt** (once, from a checkout with `.env`):

```bash
./deploy/langfuse-prompt-seed.sh
```

### Deploying

```bash
LIBRECHAT_HOST=ec2-user@HOST ./deploy/deploy-librechat.sh
LIBRECHAT_HOST=ec2-user@HOST ./deploy/deploy-librechat.sh --sync    # prompt change only
LIBRECHAT_HOST=ec2-user@HOST ./deploy/deploy-librechat.sh --check   # verify, ship nothing
```

The prompt is rendered and its YAML validated **locally, first**, so a Langfuse outage
stops the deploy before the box has been touched.

`--check` runs five assertions and reports them separately, because they fail for
different reasons: LibreChat answering, LiteLLM alive, nginx serving both ports, and —
the one that actually proves the integration — an `initialize` call to the MCP server
**from inside the api container**, asserted to come back carrying its operating rules.
Reaching the MCP server from the host proves nothing about whether the container can,
and that gap is the most likely way this deployment fails.

Registration is left **open**, which would be wrong on an internet-facing box and is
the right call here: there is no public IP, the whole box is VPC-only, and judges may
need to make their own accounts. To close it anyway, set `ALLOW_REGISTRATION=false` in
`/etc/sonyliv/librechat.env` and `sudo docker compose up -d api`.

Every `docker compose` call must be **under sudo**: the compose CLI reads `env_file`
itself, and `/etc/sonyliv/librechat.env` is 0600 root-owned by design. Docker-group
membership talks to the daemon; it does not read that file.

### Proving it works

Four questions, each aimed at one thing that has been got wrong on this data. These are
the answers the stack actually gave when the whole thing was run end to end:

**"What was peak concurrent viewership in the hour starting 2026-07-26 10:00 UTC?"**
→ calls `peak_and_average` with `grouping='total'`, answers **2,305 at 10:55:00 UTC**,
naming the measure and the window. A different number means it blended groupings.

**"Have viewers dropped in the last ten minutes?"**
→ calls `data_freshness` **first**, then declines to call it a drop because the minute
layer is not settled that far forward. This is what proves the injected rules reached
the model rather than merely being configured.

**"Give me the user ids of the people in the top session."**
→ *"This surface is aggregate-only and does not have access to per-user or per-event
data"*, and offers the aggregate answer instead. The grant would have refused it anyway;
the point is that it refuses *legibly*.

**"Which platforms were biggest, and what is their combined peak?"**
→ ranks them, then: *"It is not possible to combine the peaks of different platforms
because they peak at different instants. Summing them would invent an audience that was
never simultaneously present."* The additivity rule, held under direct pressure.

Then open Langfuse: an `AgentRun` per turn with a TOOL span per MCP call, a LiteLLM
generation with the cost, and the prompt version stamped in the system message.

### Troubleshooting

Two failures are near-certain if the config is rebuilt from scratch, and neither says
what it means. Both are already handled in `librechat.yaml.tmpl`:

**`Domain "http://host.docker.internal:8848" is not allowed`** — LibreChat blocks
outbound requests to private addresses (SSRF protection). Needs
`mcpSettings.allowedAddresses`. Use `allowedAddresses`, not `allowedDomains`: the latter
switches the whole instance to whitelist mode.

**`OAuth Required: true` and `Initialized with 1 configured server and 0 tools`** — the
MCP server answers an unauthenticated request with `401` + `WWW-Authenticate: Bearer`,
which is correct HTTP and also exactly the signal MCP's OAuth discovery looks for.
`requiresOAuth: false` on the server entry settles it. Note the log still reads as a
successful initialisation, so the only symptom is the model insisting it has no tools.

A third, less subtle: if `SONYLIV_MCP_TOKEN` differs between `/etc/sonyliv/mcp.env` and
`/etc/sonyliv/librechat.env`, every tool call 401s and the model reports that it *has no
data* rather than that it is unauthorised.

### The empty-bubble failure, and why there are two causes

The first real demo of this deployment produced **empty assistant messages** — no text,
no error, nothing in the container logs. Two independent causes, and fixing either alone
leaves it broken.

**1. No tools were attached.** A `custom` endpoint requires the person to pick the MCP
server from the chat-area dropdown, per conversation. Nobody does. And the analyst prompt
says to answer only from a tool call, so with no tools the model has no legal move: it
either invents a plausible answer or returns nothing. Measured — same prompt, same
question: without tools, `completion_tokens: 0`; with tools, a correct `viewing_trend`
call. Fixed by binding the tools to an **Agent** (`sync-agent.sh`) and making it the
default `modelSpec`, so there is no state a user can forget to set.

**2. LibreChat drops responses that carry `reasoning_content`.** Gemini 2.5 streams its
chain of thought in that field. Through the proxy directly the answer arrives intact
(144 chars of content); through LibreChat's custom endpoint the stored message is the
empty string, beside a fully populated `reasoning_content` in the trace. Fixed with
`reasoning_effort: disable` in `litellm-config.yaml`.

Underneath (2) there is a narrower one worth knowing: with Gemini's **dynamic** thinking
budget and 8 tool schemas attached, a vague question returns a candidate with zero output
parts — HTTP 200, `finish_reason: stop`, `completion_tokens: 0`, six runs out of six.
Specific questions survive because the model commits to a tool quickly. It is exactly the
open-ended question a person opens the chat and types that dies.

`gemini-2.5-pro` is therefore **not offered**. It refuses a zero thinking budget outright
(`Budget 0 is invalid. This model only works in thinking mode.`), and with thinking on
LibreChat drops its answers. A picker entry that returns empty bubbles is worse than a
short picker.

### Charts, and why code interpreter is not enabled

Asked to plot something, the agent emits a **Recharts component as a LibreChat artifact**
and the UI renders it as an interactive chart beside the conversation. That is
`artifacts: "default"` on the agent, set by `sync-agent.sh`. Without it the same question
returns a markdown table, because a table is the best it can render.

**Code interpreter cannot be self-hosted on this box.** The open-source service
(ClickHouse's `code-interpreter`) is six components built from source, and its
sandbox-runner requires KVM. This instance has no `/dev/kvm` and no `vmx`/`svm` CPU flags
— an ordinary EC2 guest, not a `.metal` one — so the sandbox cannot start and the rest
has nothing to run code in.

That leaves LibreChat's hosted Code Interpreter API, which is a key and nothing else. Set
`LIBRECHAT_CODE_API_KEY` in `/etc/sonyliv/librechat.env` and re-run the deploy;
`sync-agent.sh` adds the `execute_code` tool only when that key is present, and the agent
gains executed Python — matplotlib PNGs, file in and out.

It is deliberately **not** added without a key. A tool that is present but unconfigured
fails on every call, which reads as a broken agent rather than an unconfigured one.

Worth being clear about what it would buy: charts already work. Code interpreter buys
*executed code* — statistics the serving layer does not compute, exports, image files —
not charting.

### If the MCP dropdown does not appear

Gemini tool-calling through the chat area is the light-touch path — everything stays in
`librechat.yaml`, so a prompt change is a file write and a restart. If it misbehaves,
build a LibreChat **Agent** in the UI, attach the same `sonyliv-serving` server, and
paste `librechat/agent-instructions.txt` — which the sync writes for exactly this — into
its instructions. Same prompt, same version stamp; only the place it is stored changes.

---

## Notes

**`sonyliv-ingest` is a CLI, not a service.** It gets installed and never
restarted. `schema`, `content`, `events` and `verify` stay manual, because
applying DDL or loading a day is a decision, not a deploy step.

**`sonyliv-gen` is also installed** and can be run by hand for the live-replay
demo, or wrapped in its own unit later. With `--duration 0 --max-events 0` it runs
indefinitely.

**Rolling back by hand:**

```bash
ssh ec2-user@HOST 'sudo mv /usr/local/bin/sonyliv-api.prev /usr/local/bin/sonyliv-api \
                   && sudo systemctl restart sonyliv-api'
```

Only one generation of `.prev` is kept. Two bad deploys in a row leave you
rebuilding from a known-good commit rather than rolling back twice.
