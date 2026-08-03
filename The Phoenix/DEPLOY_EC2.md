# Deploying Phoenix on an EC2 Ubuntu instance, port 80

Verified against the identical stack running locally on 2026-08-02. Four containers, one published
port, no ClickHouse on the host (it is ClickHouse Cloud, per the problem statement's requirement
that each team load into its own service).

## What you need first

- An Ubuntu 22.04 or 24.04 EC2 instance, t3.medium or larger (the Next.js build needs ~2 GB).
- Security group inbound: **port 80 from 0.0.0.0/0**, and port 22 from your IP. Nothing else.
  `scripts/check_published_ports.sh` asserts the container side of this; the security group is
  yours to set.
- The ClickHouse Cloud credentials.

## 1. Instance setup

```bash
sudo apt-get update && sudo apt-get install -y docker.io docker-compose-v2 git
sudo usermod -aG docker ubuntu && newgrp docker
```

**If you copied the folder here with scp or a zip rather than `git clone`, restore the exec bits
first.** Both of those drop file modes, and the failure it produces is a bare "Permission denied"
that looks nothing like its cause:

```bash
chmod +x scripts/*.sh deploy/*.sh
```

`git clone` preserves the modes and needs none of this. The Docker image sets the bit itself
during the build, so the containers are unaffected either way; this is only for the scripts you
run directly on the host, such as `check_published_ports.sh` and the `init_db.sh` seeding step.

## 2. Get the code

Deploy the submission folder. It is self-contained and carries no secrets.

```bash
git clone <your-fork-url> phoenix && cd phoenix/submission/The\ Phoenix
```

## 3. Credentials

**`.env` is not in the archive.** It is gitignored, so neither the repo nor the submission zip
carries it, by design. It must be created on the host, and it is the one file a redeploy loses.
If a previous stack is still running, recover it from the container rather than retyping secrets:

```bash
docker exec phoenix-web-1 printenv | grep -E '^(CH_|LIVE_DB|LIBRECHAT_)' > .env
```

Otherwise:

```bash
cp .env.example .env
nano .env
```

Fill in, at minimum:

```
CH_HOST=<your-service>.ap-south-1.aws.clickhouse.cloud
CH_PORT=9440                 # native, used by scripts/ch.sh
CH_HTTP_PORT=8443            # HTTPS, used by the app. NOT the same port, and the app
                             # deliberately ignores CH_PORT: see frontend/src/lib/env.ts
CH_USER=default
CH_PASSWORD=<secret>

CH_DATABASE=phoenix_graded        # v1's "Original corpus". FROZEN, and NEVER equal to LIVE_DB
CH_INSIGHT_DATABASE=phoenix_live  # the ten insight tables, v2
CH_UNSEEN_DATABASE=phoenix_unseen # v1's "Unseen day" position
LIVE_DB=phoenix_live              # what the producer and ticker write into
DERIVE_PERIOD=60
```

**`CH_DATABASE` and `LIVE_DB` must name different databases.** The serving queries no longer
carry a frozen-timestamp predicate: isolation is the database name now
(`frontend/src/lib/env.ts`). Point both at one database and the producer's generated events land
inside v1's graded answers, silently, with nothing in the UI to indicate it. Observed once in a
live deploy: 2,864,457 generated rows sitting alongside the 905,558 delivered ones.

Build the frozen copy once, from whichever database the producer writes to:

```bash
FROZEN_BEFORE=2026-08-01 CUT_BEFORE='2026-07-31 23:59:59.999' \
  SRC_DB=phoenix_live DST_DB=phoenix_graded ./scripts/replicate.sh
```

It copies raw events at the cut and re-derives through the unmodified pipeline, so the result is
an independent derivation rather than a clone. Accept it when `./scripts/ground_state.sh` reports
peak **2,828** at **2026-07-26 10:56**.

Leave `LIBRECHAT_API_KEY` blank. `ALLOW_SERVER_LLM_KEY` defaults to off, which means visitors
bring their own model key and questions bill to their account, not yours. Setting it to `true`
lets any anonymous caller spend your credit; the rate limiter is per-process, not per-IP.

## 4. Build the databases

Only needed once per ClickHouse service. Skip if the databases already exist.

```bash
sudo apt-get install -y clickhouse-client   # or: curl https://clickhouse.com/ | sh

./scripts/init_db.sh phoenix_live
./scripts/init_insights.sh phoenix_live
./scripts/init_db.sh phoenix_unseen
./scripts/init_insights.sh phoenix_unseen
```

Load the data. **Content first**: orphan `content_id`s are invisible to every filtered query, and
`live_producer.sh` hard-fails on an empty content table.

```bash
CONTENT='https://drive.usercontent.google.com/download?id=1OqlA9OoXYsbUwHMLCb_qEpLewb_WTf22&export=download&confirm=t'
RAW='https://drive.usercontent.google.com/download?id=1ojIdCjM-ctbsMwdhLLFX8Inzv6JgVMRj&export=download&confirm=t'
```

Note the host: `drive.usercontent.google.com`, not `drive.google.com/uc`. At 1.8 GB Drive serves a
virus-scan interstitial instead of the file and ClickHouse fails with `EMPTY_DATA_PASSED`.

```bash
CH_DATABASE=phoenix_unseen ./scripts/ch.sh --query "
  INSERT INTO phoenix_unseen.content (content_id, title, video_type, category, show_name)
  SELECT content_id, title, video_type, category, show_name
  FROM url('$CONTENT', CSVWithNames)"

CH_DATABASE=phoenix_unseen ./scripts/ch.sh --query "
  INSERT INTO phoenix_unseen.raw_events_landing
    (content_id, video_session_id, user_id, event_type, event, event_timestamp,
     platform, app_version, country, audio_language, subtitle_language, player_version,
     session_start_epoch, video_resolution)
  SELECT content_id, video_session_id, user_id, event_type, event, event_timestamp,
     platform, app_version, country, audio_language, subtitle_language, player_version,
     session_start_epoch, video_resolution
  FROM url('$RAW', CSVWithNames)"
```

**Never `INSERT ... SELECT *` here.** It matches by position, and a positional insert against these
tables silently writes resolution strings into the wrong column without erroring, because every
column involved is a `LowCardinality(String)`.

Derive:

```bash
./scripts/derive.sh phoenix_unseen        # ~41s for 7,000,000 rows
FROM_TS='2026-07-31 00:00:00' TO_TS='2026-08-01 00:00:00' \
  CH_DATABASE=phoenix_unseen ./scripts/refresh_insights.sh
```

Seed `phoenix_live` the same way with the original corpus, then `./scripts/derive.sh phoenix_live`.

## 5. Bring the stack up

```bash
docker compose up -d --build
```

First build is 3 to 5 minutes. Four containers start: `proxy` (nginx on 80), `web` (both consoles),
`producer` (continuous event generation into `phoenix_live`), `ticker` (the derive loop).

For the Ask tab, add LibreChat. Its bind mounts must exist and be owned by the uids the images
run as, FIRST: Docker creates missing bind sources as root, and mongod (999) then dies with
`Permission denied ... /data/db/journal` and exit 100, meilisearch with exit 1. A fresh checkout
has neither directory, so this bites every first deploy.

```bash
mkdir -p librechat/data-node librechat/meili_data_v1.35.1
sudo chown -R 999:999   librechat/data-node
sudo chown -R 1000:1000 librechat/meili_data_v1.35.1
touch librechat/.env     # bound as a FILE; if absent, Docker creates a directory and the API dies

docker compose --profile chat up -d
```

The Ask tab needs `LIBRECHAT_API_KEY` and `LIBRECHAT_AGENT_ID`, which only exist once LibreChat
is running: create a key in its UI under Settings, copy the Project Assistant agent id, put both
in `.env`, then recreate `web`. Deleting `librechat/data-node` destroys that account and the key
with it. Every other view works without any of this.

## 6. Verify before you show anyone

```bash
./scripts/check_published_ports.sh      # asserts 80 is the ONLY published port
docker compose ps                       # web and ticker must read (healthy)

curl -s -o /dev/null -w "%{http_code}\n" http://localhost/
curl -s -o /dev/null -w "%{http_code}\n" http://localhost/v2
curl -s "http://localhost/api/status?dataset=unseen" | head -c 200
```

The health checks are meaningful, not cosmetic: `web` runs a real query, and `ticker` asserts its
watermark file is under five minutes old. A hung ticker and a working ticker are otherwise
indistinguishable from outside the container, which is how a permanent failure once went unnoticed
for twenty minutes while the logs printed `PASS`.

Then open `http://<ec2-public-ip>/` in a browser and check the curve renders, the filter rail is
populated, and the dataset switch flips between the corpus and the unseen day.

## 7. Operating it

```bash
docker compose logs -f ticker     # silent on success; prints the full error on failure
docker compose logs -f producer
docker compose restart web
docker compose down               # stops everything; data lives in ClickHouse Cloud
```

The derive watermark lives in a named volume (`derive-state`), so it survives a restart. Without
that it was ephemeral and every tick replayed a 3600-second window every 60 seconds.

## Known limitations, stated rather than discovered

- **Plain HTTP.** No TLS. The browser will say "Not secure". Add certbot if you want HTTPS.
- **Suffix filters prune weakly.** `video_resolution` and friends sit at positions 6 to 9 of the
  sorting key. The `p_suffix_first` projection recovers most of it (133,784 rows read becomes
  18,809), but a filter on `app_version` alone is unprunable in both orders.
- **The cumulative sum is seeded from the start of history.** A one-hour window costs the same as a
  whole-corpus window, by design, because a session that opened earlier is still watching.
  `MAX_WINDOW_DAYS = 31` in `frontend/src/lib/filters.ts` bounds the damage. The real fix is a
  checkpoint table: built, parity-verified, and parked with its measurements in
  `.archive/checkpoint-wip/WHY_PARKED.md`.
- **Daily partitioning.** The unseen day's dirty tail spans 2014 to 2026, producing 189 daily
  partitions where one holds 99 percent of the rows. `toYYYYMM` is the fix and needs a full
  rebuild of both databases, so it was not applied under time pressure.
