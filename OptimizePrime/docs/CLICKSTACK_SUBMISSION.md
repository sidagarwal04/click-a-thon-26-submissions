# CLICKSTACK_SUBMISSION — gap audit against the organiser's common requirements

> **Summary:** Audits this repo against the ClickStack evidence clause in
> [docs/upstream/SUBMISSIONS_README.md](upstream/SUBMISSIONS_README.md), which applies *in addition*
> to the SonyLIV track guidelines. Verdict tally: **3 satisfied · 6 partial · 5 missing** across 14
> required items. Every partial is an agent-sized writing task; every missing item needs a human
> (ClickHouse Cloud console SSO for screenshots, plus the hosted demo, video, fork and PR).
> **One HIGH-severity hygiene finding:** no credential has leaked, but the graded service's full
> identity — hostname, organization UUID, service UUID — is committed across 8 files and 4 commits,
> and [SUBMISSION.md](../SUBMISSION.md)'s existing secret-scan note materially undercounts it.

Audited 2026-08-02 against `HEAD` of `main`. Every PRESENT path below was opened, not inferred.

---

## 0 · Highest-severity finding first — committed identifiers for the graded service

**No secret leaked.** Verified, with the commands that prove it:

| Check | Result |
|---|---|
| `.env` ever committed? | **No** — `git log --all -- .env .env.*` is empty |
| Cloud password in tracked files or history? | **No** occurrences |
| ClickStack/HyperDX API key id or secret? | **No** occurrences |
| `CLICKSTACK_INGESTION_KEY` value? | **No** occurrences |
| Bearer / Basic / `x-api-key` headers with a literal value? | **No** occurrences |

The only password-shaped strings in tracked files are the placeholders `changeme` /
`changeme-agent` in `.env.example` and the deliberately-fake `CH_USER=guard CH_PASSWORD=guard
CH_HOST=guard-test.invalid` fixtures in `evidence/promotion/w1/codex-revalidation.md`. Both are fine.

**What HAS leaked is the graded service's identity.** Three kinds of value, none of them a
credential, all of them real:

### Leak A — the real ClickHouse Cloud service hostname

The value is the live endpoint hostname: a service-identifier subdomain plus region plus cloud
provider. It appears in **42 lines across 5 tracked files**:

| File | Lines |
|---|---|
| `evidence/graded-inventory/09-ddl-history-sonyliv.txt` | 37 lines (7, 13, 46, 238, 360–394 even, 1518, 1636, 1638, 2359, 3612, 4157, 4160–4161, 4177, 4179, 4930, 5674–5675) |
| `evidence/load-guard.txt` | 2, 6, 69 |
| `evidence/cruel/misscol.run.txt` | 15 |
| `evidence/cruel/newcol.run.txt` | 15 |

In history at commits `6355048`, `de1c361`, `c748df7` (`git log --all -S` confirms).

### Leak B — the real Cloud organization UUID and service UUID

Embedded in control-plane API URLs of the form
`https://api.clickhouse.cloud/v1/organizations/<ORG-UUID>/services/<SERVICE-UUID>/clickstack/...`.
**10 lines across 4 tracked files**:

| File | Lines |
|---|---|
| `evidence/alerting/clickstack-alerts.txt` | 2, 4, 18, 28 |
| `evidence/alerting/clickstack-alerts-BEFORE-having-fix.txt` | 2, 4, 17, 27 |
| `evidence/clickstack-dashboards.txt` | 2 |
| `evidence/clickstack/tile-verification-2026-08-01.txt` | 2 |

In history at commit `6591ae0`.

### Leak C — HyperDX dashboard object ids (LOW)

Seven dashboard ids in `docs/CLICKSTACK_DASHBOARDS.md:311`,
`docs/artifacts/2026-08-01-clickstack-dashboards.html:61`,
`evidence/clickstack/tile-verification-2026-08-01.txt:111`. These are objects *inside* the service
and are inert without an authenticated session. Noted for completeness; not worth acting on.

### Why this is HIGH and not CRITICAL — and why the existing note is wrong

No access is granted by any of the above. But A + B together are the *complete* coordinates of the
graded service — endpoint, org, service — leaving only the password unknown. That is a materially
larger exposure than the repo currently believes.

`SUBMISSION.md:24-30` already carries a secret-scan checklist item, and it is **incomplete in two
ways**:

1. It names only `evidence/load-guard.txt` and commit `6355048`. It misses
   `evidence/graded-inventory/09-ddl-history-sonyliv.txt` (37 of the 42 lines — 88% of the
   exposure), both `evidence/cruel/*.run.txt` files, and commits `de1c361` and `c748df7`.
2. It does not mention Leak B **at all** — the org and service UUIDs are a separate class of
   identifier from the hostname and are not caught by the hostname grep it recommends
   (`git log --all -S"<your-host>.clickhouse.cloud"`).

**ACTION — needs an operator decision, not an agent.** Two defensible paths; pick one deliberately
before the repo is made public or forked into the submission repo:

- **Accept and document.** No credential is exposed; rotate the Cloud password and the
  ClickStack API key after the event (already a checklist line in `SUBMISSION.md`). Cheapest, and
  honest. If chosen, correct the `SUBMISSION.md` note so it states the true blast radius.
- **Scrub.** Redact the four evidence files at `HEAD` and rewrite history across the four commits.
  History rewrite three hours before a deadline, on a checkout with concurrent agents, is a
  meaningful risk of losing work for an exposure that grants nothing.

**Recommendation: accept, rotate, and fix the note.** Do not attempt a history rewrite today.

Whichever is chosen, re-run before publishing: `gitleaks git .` plus greps for the hostname **and**
for the org/service UUID pattern.

> This file deliberately reproduces **no** leaked value — only file, line, and kind. Redacting a
> secret badly is worse than flagging it precisely.

---

## 1 · The ClickStack evidence clause, item by item

All quotes below are from [docs/upstream/SUBMISSIONS_README.md](upstream/SUBMISSIONS_README.md),
section *"Using ClickStack, Langfuse, or LibreChat?"* and the mandatory-items list above it.

The section opens with the standard this is judged against:

> "These tools run as services outside your repo, so judges only see what you capture. […] 'we had
> it running' is not evidence."

and closes the loophole:

> "Superficial inclusion (installed but not part of the actual workflow) scores nothing on the
> ClickHouse & OSS Stack criterion."

On that last point this repo is in good shape: `sonyliv observe` emits real OTLP that is read back
out of ClickStack's own ClickHouse, and the concurrency UI *is* HyperDX rather than bespoke frontend
code. The gaps below are about **capture and packaging**, not about depth of integration.

---

### R1 — Deployment / wiring configuration

**REQUIRED.** "Commit the wiring — deployment config (e.g. `docker-compose.yml` / Helm) […] Judges
must be able to see *how* it's connected, even if they don't redeploy it."

**PRESENT.**
- `docker-compose.yml` — the `clickstack` service (`clickhouse/clickstack-all-in-one`), ports 8080
  UI / 8000 API / 4317 OTLP-gRPC / 4318 OTLP-HTTP, under the `oss` profile. Carries the two
  non-obvious operational facts inline as comments (`tty: true` or it exits 129; OTLP does not bind
  until a team exists).
- `tools/clickstack-bootstrap.sh` — team registration and ingestion-key mint for the local stack.
- `Makefile` targets `stack-up` / `clickstack`.

**VERDICT: satisfied.**

**ACTION.** None. Ensure `docker-compose.yml` is inside the team folder when R13 is done.

---

### R2 — `.env.example` with secrets redacted

**REQUIRED.** "an `.env.example` with **secrets redacted**"

**PRESENT.** `.env.example` (tracked; `.env` correctly gitignored via `.env` + `.env.*` +
`!.env.example`).

**Redaction verified — clean.** Read line by line:

| Variable | Value committed | Assessment |
|---|---|---|
| `CH_HOST` | `your-service.clickhouse.cloud` | placeholder, not the real host |
| `CH_PASSWORD`, `CS_PASSWORD`, `CH_API_KEY_ID`, `CH_API_KEY_SECRET`, `CLICKSTACK_CONNECTION_ID` | empty | correct |
| `CH_PASSWORD_LOCAL`, `AGENT_PASSWORD` | `changeme`, `changeme-agent` | obvious placeholders |
| `CS_EMAIL` | `team@clickathon.local` | non-routable placeholder domain |
| `CH_USER`, `CH_DATABASE`, ports, URLs | `default`, `sonyliv`, `8443`, `localhost` | non-secret |

**No hostname, password, service id or token has leaked into this file.** It is genuinely redacted.

**VERDICT: partial** — redaction is correct, *completeness* is not.

Six variables the code actually reads are absent from `.env.example`, so a judge cannot see the full
wiring from it:

| Missing var | Read by | Why it matters |
|---|---|---|
| **`CLICKSTACK_INGESTION_KEY`** | `internal/config/clickstack.go:31` | **This is the OTLP secret.** The one variable most load-bearing for the ClickStack integration is the one not declared. Requesting a redacted `.env.example` and omitting the actual secret from it inverts the requirement. |
| `CLICKSTACK_SERVICE_NAME` | `internal/config/clickstack.go:32` | default `sonyliv-pipeline`; the value judges filter dashboards by |
| `CLICKSTACK_SKIP_APPLY` | `tools/clickstack-cloud.sh` | control-plane-only runs |
| `GRADED_DB` | `tools/build-model.sh` | graded-vs-scratch safety switch |
| `CH_LOCAL_USER`, `CH_FLAG` | `tools/ch`, loaders | local connection |

`docs/OBSERVABILITY.md:101-104` documents all three `CLICKSTACK_*` vars and says "see
`.env.example`" — a cross-reference to a file that does not contain them.

**ACTION — agent, ~5 minutes.** Add the six variables to `.env.example` with empty or placeholder
values and a one-line comment each, under the existing ClickStack heading. Adds nothing secret;
closes the requirement. **Do not** let this edit collide with concurrent agents — it is a
single-hunk append.

---

### R3 — The integration code itself

**REQUIRED.** "and the integration code itself (SDK setup, OTel collector config, custom
endpoints)."

**PRESENT.**
- `internal/otelemit/` — `client.go` (OTLP/HTTP JSON POST to `/v1/metrics`, `/v1/logs`,
  `/v1/traces`; `authorization` header), `types.go`, `ids.go`, plus `client_test.go`,
  `otelemit_test.go`, `types_test.go`.
- `internal/config/clickstack.go` — endpoint / key / service-name loading.
- `cmd/sonyliv/observe.go` — the emitter entry point (`sonyliv observe -target cloud`).
- `internal/pipelinehealth/` — the three signal sources (watermark, build stages, reconcile gate).
- `tools/clickstack-cloud.sh`, `clickstack-sources.sh`, `clickstack-observability.sh`,
  `clickstack-alerts.sh`, `clickstack-artifact.sh`, `clickstack-bootstrap.sh`.

Note this is deliberately **not** the OpenTelemetry Go SDK — a ~250-line stdlib-only OTLP/HTTP JSON
client, with the reasoning recorded at `docs/OBSERVABILITY.md:5-8`. That is a defensible choice but
a judge skimming for `go.opentelemetry.io` in `go.mod` will not find it. Say so out loud in the
team README.

**VERDICT: satisfied.**

**ACTION.** None for the code. When writing the team README, state in one sentence that the OTLP
client is hand-rolled stdlib and why, so its absence from `go.mod` reads as a decision rather than
an omission.

---

### R4 — OTel collector / ingestion configuration

**REQUIRED.** "**ClickStack** — include your OTel collector / ingestion config"

**PRESENT — partially, and not as a file.** There is **no** committed collector YAML
(no `otel-collector-config.yaml`, no `otelcol` config anywhere in the tree). This is *correct
architecture* but *incomplete evidence*: the `clickhouse/clickstack-all-in-one` image ships its own
OTel collector, which we run unmodified. Our configuration surface is therefore:

- `docker-compose.yml` — the collector's port bindings (4317/4318).
- `tools/clickstack-bootstrap.sh` — team creation, which is what makes the collector bind, and
  ingestion-key mint.
- `internal/config/clickstack.go` — `CLICKSTACK_OTLP` endpoint and `CLICKSTACK_INGESTION_KEY`.
- `docs/OBSERVABILITY.md` — the wire contract that was verified against it.

**VERDICT: partial.** The config exists and is real; nothing states that the collector is the
bundled one used as-is, so its absence looks like a missing file rather than a deliberate choice.

**ACTION — agent, ~10 minutes.** One paragraph in the team README: "we run the
`clickstack-all-in-one` bundled OTel collector unmodified; there is no collector YAML because we
changed none of it. Our ingestion config is `CLICKSTACK_OTLP` + `CLICKSTACK_INGESTION_KEY`
(`internal/config/clickstack.go`), the ports in `docker-compose.yml`, and the team/key bootstrap in
`tools/clickstack-bootstrap.sh`." Link the three files.

---

### R5 — Name the ClickHouse service and tables ClickStack writes to

**REQUIRED.** "state which ClickHouse service and tables it writes to"

This is the item most likely to be quietly wrong, so it was checked hardest. **The answer is that
there are two distinct ClickHouse instances and they must not be conflated.**

**PRESENT — the read path (dashboards).**
HyperDX built into the graded **ClickHouse Cloud service**, reading database **`sonyliv`** directly
with no separate connection string or IP allowlist (`docs/CLICKSTACK.md:12-14, 66-68`). Tables and
views it reads:

| Object | Named at |
|---|---|
| `v_concurrency_minute_total`, `v_concurrency_minute_stateless` | `docs/CLICKSTACK.md:98-105` |
| the 7 dashboards' full source list (27 named sources) | `tools/clickstack-cloud.sh`, `docs/CLICKSTACK_DASHBOARDS.md` |
| `session_intervals`, `cc_minute_delta` | `tools/clickstack-cloud.sh:525-526` |
| `system.query_log` (source id `6a6dd4ac233f0475ad40cecd`) | `docs/OBSERVABILITY.md:88-92` |
| defining SQL | `sql/20_views.sql`, `sql/87_viz.sql` |

**PRESENT — the write path (OTLP).**
Our telemetry does **not** land in the graded service. `docs/OBSERVABILITY.md:10-11` and
`docs/CLICKSTACK.md:205` both verify the Cloud service **has no OTLP path — no `otel_*` tables**.
OTLP writes go to the **local `clickstack-all-in-one` container's own bundled ClickHouse
(26.5.6)**, into:

- `otel_metrics_gauge`, `otel_logs`, `otel_traces`, `hyperdx_sessions`
  (`docs/OBSERVABILITY.md:115, 133, 153, 188`; `internal/otelemit/types.go:11`)
- under `service.name = sonyliv-pipeline`

`docs/OBSERVABILITY.md:115-160` shows the actual rows read back out of those tables after a real
run — this is genuinely verified, not asserted.

**VERDICT: partial.** Both destinations are real and correctly documented **in `docs/`**. Two gaps:

1. **Not stated in any submission-facing file.** Neither `README.md` nor `SUBMISSION.md` names the
   destination tables. The requirement is that the *submission* states it.
2. **The read/write split must be stated explicitly, or it reads as a misrepresentation.** A judge
   who sees "ClickStack integration" plus "ClickHouse Cloud service `sonyliv`" will reasonably
   assume the telemetry lands there. It does not. Saying so plainly — *dashboards read the graded
   Cloud service; OTLP telemetry writes to the ClickStack container's bundled ClickHouse, because
   Cloud exposes no OTLP endpoint* — is both more accurate and more impressive than blurring it.

**ACTION — agent, ~15 minutes.** Add a "ClickStack destinations" table to the team README with two
rows (read path / write path), each naming instance, database, and tables, sourced from the paths
above. Do **not** paste the real service hostname or service UUID into it — "the graded ClickHouse
Cloud service, database `sonyliv`" is sufficient identification and keeps §0 from getting worse.

---

### R6 — Real screenshots of the dashboards actually used

**REQUIRED.** "capture the dashboards or searches you actually used (screenshots in the README plus
a live walkthrough in the video)" — and, categorically: "**Show it live** in your hosted demo and
demo video - a screenshot alone is not proof of integration."

**PRESENT.** No HyperDX UI screenshot exists. What exists instead:

- `evidence/clickstack/dashboard-preview.png` — a **headless-Chrome rendering of our own
  `dashboard-preview.html`**, drawn from live read-only SELECTs. Data-faithful, but it is our HTML,
  not the HyperDX UI.
- `evidence/clickstack/tile-verification-2026-08-01.txt` — all 53 tiles across 7 dashboards executed
  through HyperDX's own `query_tile` path with returned values. Strong *functional* proof.
- `evidence/clickstack-dashboards.txt`, `docs/CLICKSTACK_DASHBOARDS.md` (41 tiles documented),
  `docs/artifacts/2026-08-01-clickstack-dashboards.html`.

`evidence/clickstack/README.md` is admirably honest about this and states the cause: hosted HyperDX
authenticates through ClickHouse Cloud console **SSO**, and the Cloud API key that drives
`tools/clickstack-cloud.sh` and the MCP can query everything but cannot mint a browser session.
Confirmed twice on 2026-08-01.

**VERDICT: missing** (as the requirement is written — real UI screenshots embedded in the README).

**ACTION — HUMAN REQUIRED. Cannot be done by an agent, at any cost, for a structural reason.**

1. Sign in to the ClickHouse Cloud console (SSO) and open HyperDX.
2. **First** run `tools/clickstack-cloud.sh` — per `docs/CLICKSTACK.md:38-44`, the current
   27-source / 12-filter deployment has **not** been pushed to Cloud; only the older
   24-source / 8-filter deployment is proven live. Screenshotting before this shows the stale one.
3. Warm the service: `tools/ch -c "SELECT 1"`.
4. Set the time range to **2026-07-14 → 2026-07-26** for dashboards 1–4 and 7; a recent range for
   5–6 (pipeline health, query cost). The default 15-minute window is **empty** — data ends
   2026-07-26. Screenshotting without this yields blank panels.
5. Capture the dashboards listed in `docs/CLICKSTACK_DASHBOARDS.md`, commit the PNGs into the team
   folder, and embed them in the team README.

Steps 2–4 are the ones that go wrong. Do them in order.

---

### R7 — Live demonstration in the hosted demo

**REQUIRED.** "**Show it live** in your hosted demo […] the hosted demo and the 2–3 minute video
must walk through ClickStack live and explain its role in the architecture." The mandatory list
additionally requires a `README.md` that "must include a **hosted demo link**".

**PRESENT.** **ABSENT.** `README.md:48` states plainly: "**Hosted demo:** not yet published."
`demo/run.sh --offline`, `demo/SCRIPT.md`, `demo/REPLAY.md` and `demo/chaos.sh` exist as a local
demo but nothing is hosted.

**VERDICT: missing.**

**ACTION — HUMAN REQUIRED.** Decide what "hosted" means for this submission and publish it. The
lowest-risk option given ~3 hours: the HyperDX dashboard URLs in `docs/CLICKSTACK_DASHBOARDS.md`
*are* a hosted surface, but they are behind Cloud SSO and judges cannot open them — so they do not
satisfy this alone. Realistic minimum: publish a static walkthrough page and make the video carry
the live proof. Then put the link in the team README.

---

### R8 — Live ClickStack walkthrough in the 2–3 minute demo video

**REQUIRED.** "**Demo video** (**mandatory**) — a recorded video, 2–3 minutes", and "the hosted demo
and the 2–3 minute video must walk through ClickStack live".

**PRESENT.** **ABSENT.** No video file and no video link in any tracked file.

**VERDICT: missing.**

**ACTION — HUMAN REQUIRED.** Record 2–3 minutes. The ClickStack segment is the graded part: show
the HyperDX dashboards live with the correct time range, change a filter and show the concurrency
curve move, then run `./bin/sonyliv observe -target cloud` and show the emitted metric appear.
`demo/SCRIPT.md` is the existing script to adapt. Be ready for the obvious question — one health
flag reads `hour_tier_complete=false`; the answer is at `docs/OBSERVABILITY.md:47-56` and it is the
truthful reading on a dataset that stops mid-hour, not a fault.

---

### R9 — Explain ClickStack's role in the README architecture section

**REQUIRED.** "**Explain its role** in your README's architecture section: what part of the pipeline
runs through the tool."

**PRESENT.** The *explanation* exists and is strong — `docs/CLICKSTACK.md:16-21` ("Why ClickStack is
the chart, not just the telemetry"), `docs/OBSERVABILITY.md:17-21` (the "if I delete ClickStack,
does the demo stop doing something a judge saw?" test), `docs/ARCHITECTURE.md`. `README.md:2-3`
mentions it in one line.

**VERDICT: partial.** The content is in `docs/`, not in a submission README's architecture section,
and the team README does not exist yet (R13).

**ACTION — agent, ~15 minutes.** Lift the two paragraphs above into the team README's Architecture
section. The strongest sentence to lead with is the deletion test: the demo's freshness indicator is
read back out of ClickStack's own ClickHouse, so removing ClickStack removes a number judges saw.

---

### R10 — Hosted demo link present in the README

**REQUIRED.** "`README.md` (**mandatory**) — must include a **hosted demo link**, and this demo link
itself must cover the details required by your track's submission guidelines".

**PRESENT.** **ABSENT** — see R7.

**VERDICT: missing.** Tracked separately from R7 because this is a hard README-completeness gate,
not just a demo gate.

**ACTION — HUMAN, then agent.** Human publishes; agent inserts the link into the template.

---

### R11 — Pitch deck in PDF

**REQUIRED.** "**Pitch deck in PDF format** (**mandatory**) — e.g. `pitch-deck.pdf`"

**PRESENT.** `deck/checkpoint1/deck.pdf` (509 KB, built 2026-08-02 from `deck/checkpoint1/deck.html`
via `deck/checkpoint1/build.sh`; see `deck/checkpoint1/README.md`).

**VERDICT: partial.** A PDF exists and is current, but it is named and scoped as *checkpoint 1*, not
as the final pitch deck, and it lives outside any team folder.

**ACTION — agent, ~5 minutes** (content review is human). Copy to the team folder as
`pitch-deck.pdf`. A human should confirm the checkpoint-1 content is the story being pitched — in
particular whether it states the peak as 2,917 or 2,927, which is the open sign-off in
[ADR 0031](adr/0031-point-activity-user-attribution-and-the-densify-recipe.md).

---

### R12 — Architecture artifact

**REQUIRED.** "**Architecture** (**mandatory**) — […] other tracks may cover it within the
`README.md` or as separate screenshots/diagrams"

**PRESENT.** `docs/ARCHITECTURE.md`; `docs/artifacts/` (the 4-part deep dive:
`deep-1-data`, `deep-2-model`, `deep-3-correctness`, `deep-4-scale-ops`);
`docs/artifacts/2026-08-01-mentor-checkpoint.html` (11 diagrams).

**VERDICT: partial** — content is more than sufficient; it is not yet in a submission-facing README
or team folder.

**ACTION — agent, ~10 minutes.** Summarise into the team README's Architecture section and link the
artifacts.

---

### R13 — Self-contained team folder, and the PR

**REQUIRED.** "Create a folder at the root of the repo, named after your **team** […] Keep your
submission self-contained within your team's folder." Then: "Open a **pull request** against this
repository with the title: `[Submission] Your Team Name`".

**PRESENT.** **ABSENT.** No fork of the organiser repo and no team folder exists. `SUBMISSION.md`
lists this as an open blocker.

**VERDICT: missing.** This is the packaging step that every other item lands inside — nothing else
can be marked done until it exists.

**ACTION — HUMAN (fork + PR), agent can assemble the folder.** Fork the organiser repo, create
`<TeamName>/`, and populate: source, team `README.md` (organiser template), architecture,
`pitch-deck.pdf`, ClickStack screenshots, `docker-compose.yml`, `.env.example`, demo + video links.
Confirm `tools/fetch_data.sh`, `demo/run.sh --offline` and `make ci` all work from an anonymous
clone with no `.env`.

---

### R14 — Project source code

**REQUIRED.** "**Project source code** (**mandatory**)"

**PRESENT.** `cmd/`, `internal/`, `sql/`, `tools/`, `queries/`, `tests/`, `policy/`, `demo/`,
`Makefile`, `go.mod`, `devbox.json`.

**VERDICT: satisfied.**

**ACTION.** None beyond R13 packaging.

---

## 2 · Tally

**14 items · 3 satisfied · 6 partial · 5 missing.**

| Verdict | Count | Items |
|---|---|---|
| **Satisfied** | 3 | R1 deployment config · R3 integration code · R14 source code |
| **Partial** | 6 | R2 `.env.example` completeness · R4 collector-config statement · R5 destinations not in a submission file · R9 role not in team README · R11 deck not final/packaged · R12 architecture not packaged |
| **Missing** | 5 | R6 real screenshots · R7 hosted demo · R8 video walkthrough · R10 demo link in README · R13 team folder + PR |

Every one of the 6 partials is an agent-sized writing task. Every one of the 5 missing items needs a
human.

### What only a human can do

| # | Task | Why an agent cannot |
|---|---|---|
| R6 | HyperDX UI screenshots | hosted HyperDX is behind Cloud console SSO; the API key drives the control and query planes but cannot mint a browser session (confirmed twice, 2026-08-01) |
| R7 / R10 | Publish the hosted demo | requires an account and a deploy decision |
| R8 | Record the 2–3 minute video | it is a recording |
| R13 | Fork + open the PR | requires the operator's GitHub identity |
| §0 | Decide accept-vs-scrub on the leaked identifiers | a judgement call with a history-rewrite risk |
| R11 | Confirm the pitch's headline number (2,917 vs 2,927) | ADR 0031 explicitly requires operator sign-off |

### What an agent can finish in under an hour

1. **R2** — add the six missing env vars to `.env.example`, `CLICKSTACK_INGESTION_KEY` first.
2. **R5** — write the read-path / write-path destinations table; state plainly that OTLP does not
   land in the graded Cloud service and why.
3. **R4** — the one paragraph explaining that the bundled collector is used unmodified.
4. **R9 / R12** — draft the team README from the organiser template, with the architecture section
   and the ClickStack role, leaving link placeholders for demo and video.
5. **§0** — correct the `SUBMISSION.md:24-30` secret-scan note to the true blast radius, once the
   operator has chosen accept-vs-scrub.

### Ordering, given a 12:00 IST close

The screenshots (R6) gate the README (R9/R12) which gates the folder (R13) which gates the PR. And
R6 itself is gated on running `tools/clickstack-cloud.sh` first, or the captures show a stale
24-source deployment. **Start the human with `tools/clickstack-cloud.sh` immediately**; the agent
work above runs in parallel and none of it blocks the human.
