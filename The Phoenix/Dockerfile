# The console image. Also the base for the ingest and derive workers, because they need the same
# thing the app needs: the repo's sql/ and scripts/ trees plus the clickhouse client.
#
# ONE IMAGE, THREE ROLES. web, producer and ticker differ only in their command. A separate
# slimmer image per worker would save a few hundred MB and cost a second Dockerfile to keep in
# step with this one, which is the trade this project has already lost once elsewhere.
FROM node:20-bookworm-slim

# ca-certificates for the HTTPS connection to ClickHouse Cloud, curl to fetch the client,
# flock (util-linux) because derive_tick.sh serialises ticks on a lock file.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl util-linux tzdata \
 && rm -rf /var/lib/apt/lists/*

# The same binary scripts/ch.sh expects on PATH, taken from the official APT repository.
#
# THIS REPLACED A PINNED GITHUB RELEASE TARBALL, which failed on a clean EC2 build with exit 126.
# The cause is worth recording because it is a generic trap: `curl -sSL` without `-f` treats a 404
# as success and writes the HTML error page to the output file. `tar` then extracts nothing, the
# expected doinst.sh does not exist, and the shell reports 126 (found but not executable) rather
# than anything resembling "that download 404'd". Any pinned release URL is one upstream retag
# away from the same failure.
#
# The APT repository is the vendor's supported path, resolves the current stable itself, and fails
# loudly when it cannot. clickhouse-client pulls clickhouse-common-static as a dependency.
RUN curl -fsSL 'https://packages.clickhouse.com/rpm/lts/repodata/repomd.xml' >/dev/null 2>&1 || true \
 && apt-get update \
 && apt-get install -y --no-install-recommends gnupg dirmngr \
 && GNUPGHOME="$(mktemp -d)" && export GNUPGHOME \
 && gpg --no-default-keyring --keyring /usr/share/keyrings/clickhouse-keyring.gpg \
        --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys 3A9EA1193A97B548BE1457D48919F6BD2B48D754 \
 && rm -rf "$GNUPGHOME" && unset GNUPGHOME \
 && chmod a+r /usr/share/keyrings/clickhouse-keyring.gpg \
 && echo "deb [signed-by=/usr/share/keyrings/clickhouse-keyring.gpg] https://packages.clickhouse.com/deb stable main" \
      > /etc/apt/sources.list.d/clickhouse.list \
 && apt-get update \
 && apt-get install -y --no-install-recommends clickhouse-client \
 && rm -rf /var/lib/apt/lists/* \
 && clickhouse client --version

WORKDIR /app

# Dependencies first, so a source edit does not reinstall node_modules.
COPY frontend/package.json frontend/package-lock.json* frontend/
RUN cd frontend && npm ci

COPY . .

# The image must not depend on the host's file modes. A checkout transferred by scp without -p, or
# unpacked from a zip, arrives with every script non-executable, and the containers then fail at
# run time with a bare "Permission denied" that looks nothing like its cause. Setting the bit here
# makes the image correct regardless of how the tree reached the build host.
RUN chmod +x scripts/*.sh deploy/*.sh 2>/dev/null || true

RUN cd frontend && npm run build

# THE APP READS THE REPO AT RUNTIME, which is why the whole tree is copied rather than just the
# build output. lib/sql.ts reads ../sql/queries/serving/*.sql and lib/insights.ts reads
# ../sql/insights/benchmark/*.sql on every request, and lib/env.ts reads ../.env. That is
# deliberate: it is what makes the query text on screen provably the text that executed. A
# standalone Next.js output would 500 on every route.
ENV NODE_ENV=production
ENV PORT=3200
WORKDIR /app/frontend
EXPOSE 3200
CMD ["npm", "run", "start"]
