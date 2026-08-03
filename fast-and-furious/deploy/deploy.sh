#!/usr/bin/env bash
#
# Build the ingest binaries and install them on the EC2 box over SSH.
#
#   DEPLOY_HOST=ec2-1-2-3-4.compute.amazonaws.com ./deploy/deploy.sh
#
# Design notes, because a few of these look arbitrary and aren't:
#
#   * Builds LOCALLY and ships the artifact. The box needs no Go toolchain, the
#     build is reproducible, and what lands is exactly what `make check` just
#     tested. Building on the box would also mean putting the source there.
#
#   * Discovers the command list from ingest/cmd/ rather than hardcoding it, so
#     a new binary (sonyliv-api) is picked up with no change here.
#
#   * Never writes ClickHouse credentials. They live in /etc/sonyliv/sonyliv.env,
#     provisioned out of band, so no CH secret passes through the deploy path.
#     See deploy/README.md for the one-time box setup.
#
#   * Restarts EVERY unit in DEPLOY_SERVICES, skipping any that is not installed.
#     Both long-running services share the binaries, so restarting only one left
#     the other running last deploy's code — silently, because it stayed healthy.
#     Order matters and the default order is the right one: sonyliv-mock produces
#     through sonyliv-api, so the API restarts first.
#
# Exit codes: 0 ok, 1 usage/preflight, 2 build failed, 3 transfer/verify failed,
#             4 service failed to come up (binaries rolled back).

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration. Environment wins; flags override.
# ---------------------------------------------------------------------------
DEPLOY_HOST="${DEPLOY_HOST:-}"
# User, key and port are deliberately EMPTY by default rather than guessed. An
# empty value means "say nothing and let ssh_config decide", so a Host block
# carrying HostName/User/IdentityFile makes `DEPLOY_HOST=alias ./deploy.sh`
# work with nothing else set. Defaulting to ec2-user and ~/.ssh/id_rsa would
# override that config and fail on a box whose user is `ubuntu`.
DEPLOY_USER="${DEPLOY_USER:-}"
DEPLOY_KEY="${DEPLOY_KEY:-}"
DEPLOY_PORT="${DEPLOY_PORT:-}"
# Space-separated, restarted in this order. DEPLOY_SERVICE (singular) is still
# honoured so existing invocations keep working.
DEPLOY_SERVICES="${DEPLOY_SERVICES:-${DEPLOY_SERVICE:-sonyliv-api sonyliv-mock}}"
DEPLOY_PREFIX="${DEPLOY_PREFIX:-/usr/local/bin}"

# unit=url pairs. Per-unit rather than one URL, because the two services do not
# listen the same way: the API is plaintext on loopback:8080 and the dashboard is
# TLS on :443. A single shared URL could only ever check one of them, which is how
# a stale mock passed a green deploy.
#
# These defaults match the deployed configuration, so `DEPLOY_HOST=sonyliv
# ./deploy/deploy.sh` needs no environment at all. A legacy DEPLOY_HEALTH_URL is
# applied to the first unit only, since that is what it used to mean.
if [[ -n "${DEPLOY_HEALTH_URL:-}" ]]; then
    DEPLOY_HEALTH="${DEPLOY_HEALTH:-${DEPLOY_SERVICES%% *}=${DEPLOY_HEALTH_URL}}"
fi
DEPLOY_HEALTH="${DEPLOY_HEALTH:-sonyliv-api=http://127.0.0.1:8080/healthz sonyliv-mock=https://127.0.0.1/healthz}"

DRY_RUN=0
SKIP_CHECKS=0
NO_RESTART=0
ONLY=""

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODULE_DIR="$REPO_ROOT/ingest"
BUILD_DIR="$MODULE_DIR/bin/linux-amd64"

usage() {
    sed -n '3,28p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
    cat <<'USAGE'

Flags:
  --dry-run        Print the build and remote plan, change nothing
  --skip-checks    Skip `make check` (tests, vet, gofmt)
  --no-restart     Install binaries but do not touch any service
  --only NAME      Build and ship only this binary (repeatable)
  -h, --help       This text

Environment:
  DEPLOY_HOST        EC2 host, or an ssh_config Host alias (required)
  DEPLOY_USER        SSH user                  [from ssh_config]
  DEPLOY_KEY         private key path          [from ssh_config / agent]
  DEPLOY_PORT        SSH port                  [from ssh_config, else 22]
  DEPLOY_SERVICES    units to restart, in order, space-separated
                     [sonyliv-api sonyliv-mock]
  DEPLOY_PREFIX      install directory         [/usr/local/bin]
  DEPLOY_HEALTH      unit=url pairs, polled ON the box with -k (loopback, so
                     cert verification proves nothing). A unit with no pair is
                     restarted but not health-checked; DEPLOY_HEALTH="" disables
                     the checks entirely.
                     [sonyliv-api=http://127.0.0.1:8080/healthz
                      sonyliv-mock=https://127.0.0.1/healthz]
USAGE
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)     DRY_RUN=1; shift ;;
        --skip-checks) SKIP_CHECKS=1; shift ;;
        --no-restart)  NO_RESTART=1; shift ;;
        --only)        ONLY="${ONLY} $2"; shift 2 ;;
        -h|--help)     usage; exit 0 ;;
        *)             echo "unknown flag: $1" >&2; usage >&2; exit 1 ;;
    esac
done

log()  { printf '\033[1m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[33mwarn:\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[31merror:\033[0m %s\n' "$*" >&2; exit "${2:-1}"; }

COMMON_OPTS=(
    -o BatchMode=yes
    -o ConnectTimeout=10
    # accept-new, not no: the first connection is trusted and pinned, but a
    # later host-key CHANGE still fails. StrictHostKeyChecking=no would accept
    # a substituted host silently.
    -o StrictHostKeyChecking=accept-new
)
# Only pass -i / -p when explicitly asked for, so an ssh_config Host block is
# not overridden by a default this script invented.
[[ -n "$DEPLOY_KEY" ]] && COMMON_OPTS+=(-i "$DEPLOY_KEY")

# ssh takes -p for the port; scp takes -P, where -p means "preserve times".
# Passing the ssh form to scp silently turns the port number into a filename.
SSH_OPTS=("${COMMON_OPTS[@]}")
SCP_OPTS=("${COMMON_OPTS[@]}")
if [[ -n "$DEPLOY_PORT" ]]; then
    SSH_OPTS+=(-p "$DEPLOY_PORT")
    SCP_OPTS+=(-P "$DEPLOY_PORT")
fi

# Bare host when no user is given, so ssh_config's User applies.
TARGET="${DEPLOY_USER:+${DEPLOY_USER}@}${DEPLOY_HOST}"

# shellcheck disable=SC2029  # deliberate: the command is built and expanded
# locally, then sent as one remote string with inner values single-quoted.
ssh_run() { ssh "${SSH_OPTS[@]}" "$TARGET" "$@"; }

# sha256 tool differs between macOS (shasum) and Linux (sha256sum).
if command -v sha256sum >/dev/null 2>&1; then
    sha256_of() { sha256sum "$1" | cut -d' ' -f1; }
elif command -v shasum >/dev/null 2>&1; then
    sha256_of() { shasum -a 256 "$1" | cut -d' ' -f1; }
else
    die "need sha256sum or shasum to verify the transfer"
fi

# ---------------------------------------------------------------------------
# 1. Preflight. Fail before building, not after.
# ---------------------------------------------------------------------------
log "preflight"

[[ -n "$DEPLOY_HOST" ]] || die "DEPLOY_HOST is not set (see --help)"
command -v go >/dev/null 2>&1 || die "go is not on PATH"
[[ -d "$MODULE_DIR" ]] || die "no Go module at $MODULE_DIR"

# Under --dry-run these are reported but not fatal: printing the plan should not
# require a usable key, since nothing is going to be connected to.
key_problem=""
if [[ -z "$DEPLOY_KEY" ]]; then
    : # no key specified: ssh_config / agent decides, nothing to validate here
elif [[ ! -r "$DEPLOY_KEY" ]]; then
    key_problem="cannot read SSH key: $DEPLOY_KEY"
else
    # ssh refuses a group/world-readable private key, and the error it gives is
    # easy to misread as an auth failure.
    key_mode="$(stat -f '%Lp' "$DEPLOY_KEY" 2>/dev/null || stat -c '%a' "$DEPLOY_KEY")"
    [[ "$key_mode" == "600" || "$key_mode" == "400" ]] \
        || key_problem="SSH key $DEPLOY_KEY is mode $key_mode; run: chmod 600 $DEPLOY_KEY"
fi
if [[ -n "$key_problem" ]]; then
    if [[ "$DRY_RUN" == 1 ]]; then
        warn "$key_problem"
    else
        die "$key_problem"
    fi
fi

VERSION="$(git -C "$REPO_ROOT" describe --tags --always --dirty 2>/dev/null \
            || git -C "$REPO_ROOT" rev-parse --short HEAD)"
STAGE="/tmp/sonyliv-deploy-${VERSION}.$$"

# Discover the binaries to build. Deliberately not `mapfile`: macOS still ships
# bash 3.2 as /bin/bash, where mapfile does not exist.
ALL_CMDS=()
while IFS= read -r dir; do
    ALL_CMDS+=("$(basename "$dir")")
done < <(find "$MODULE_DIR/cmd" -mindepth 1 -maxdepth 1 -type d | sort)
[[ ${#ALL_CMDS[@]} -gt 0 ]] || die "no commands found under $MODULE_DIR/cmd"

if [[ -n "$ONLY" ]]; then
    CMDS=()
    for want in $ONLY; do
        # shellcheck disable=SC2076
        [[ " ${ALL_CMDS[*]} " =~ " ${want} " ]] \
            || die "--only ${want}: no such command (have: ${ALL_CMDS[*]})"
        CMDS+=("$want")
    done
else
    CMDS=("${ALL_CMDS[@]}")
fi

log "host      ${TARGET}${DEPLOY_PORT:+:$DEPLOY_PORT}"
log "version   ${VERSION}"
log "binaries  ${CMDS[*]}"
log "install   ${DEPLOY_PREFIX}"
log "services  ${DEPLOY_SERVICES}"

if [[ "$DRY_RUN" == 1 ]]; then
    log "dry run: would build ${CMDS[*]} for linux/amd64, stage in ${STAGE},"
    log "         verify sha256, install atomically into ${DEPLOY_PREFIX},"
    if [[ "$NO_RESTART" == 1 ]]; then
        log "         and leave ${DEPLOY_SERVICES} untouched (--no-restart)"
    else
        log "         then restart each of ${DEPLOY_SERVICES} whose unit is installed"
    fi
    exit 0
fi

# Reachability, before spending time on a build.
ssh_run true 2>/dev/null || die "cannot ssh to ${TARGET}${DEPLOY_PORT:+:$DEPLOY_PORT}${DEPLOY_KEY:+ with $DEPLOY_KEY}.
  If this is an RSA key older than a few years, OpenSSH >= 8.8 rejects the legacy
  ssh-rsa signature algorithm and reports it as 'Permission denied (publickey)'.
  Check with: ssh -v ${SSH_OPTS[*]} ${TARGET} true"

# ---------------------------------------------------------------------------
# 2. Gate on the existing check target.
# ---------------------------------------------------------------------------
if [[ "$SKIP_CHECKS" == 1 ]]; then
    warn "skipping tests, vet and gofmt (--skip-checks)"
else
    log "make check"
    make -C "$MODULE_DIR" check || die "checks failed; fix or pass --skip-checks" 2
fi

# ---------------------------------------------------------------------------
# 3. Cross-compile.
# ---------------------------------------------------------------------------
log "building for linux/amd64"
rm -rf "$BUILD_DIR" && mkdir -p "$BUILD_DIR"
for cmd in "${CMDS[@]}"; do
    ( cd "$MODULE_DIR" && CGO_ENABLED=0 GOOS=linux GOARCH=amd64 \
        go build -trimpath -ldflags '-s -w' -o "$BUILD_DIR/$cmd" "./cmd/$cmd" ) \
        || die "build failed: $cmd" 2
    printf '    %s (%s)\n' "$cmd" "$(du -h "$BUILD_DIR/$cmd" | cut -f1 | tr -d ' ')"
done

# ---------------------------------------------------------------------------
# 4. Ship and verify.
# ---------------------------------------------------------------------------
log "staging in ${STAGE}"
ssh_run "mkdir -p '$STAGE'"
scp -q "${SCP_OPTS[@]}" "$BUILD_DIR"/* "$TARGET:$STAGE/" \
    || die "scp failed" 3

log "verifying checksums"
for cmd in "${CMDS[@]}"; do
    local_sum="$(sha256_of "$BUILD_DIR/$cmd")"
    remote_sum="$(ssh_run "sha256sum '$STAGE/$cmd' | cut -d' ' -f1")"
    [[ "$local_sum" == "$remote_sum" ]] \
        || die "checksum mismatch for $cmd (local $local_sum, remote $remote_sum)" 3
    printf '    %s ok\n' "$cmd"
done

# ---------------------------------------------------------------------------
# 5-7. Install atomically, restart, health-check, roll back on failure.
#
# The whole sequence runs server-side in one shot so a dropped connection cannot
# leave the box half-installed.
# ---------------------------------------------------------------------------
log "installing and restarting"
set +e
ssh_run "sudo bash -s -- '$STAGE' '$DEPLOY_PREFIX' '$DEPLOY_SERVICES' '$DEPLOY_HEALTH' \
         '$VERSION' '$NO_RESTART' ${CMDS[*]}" <<'REMOTE'
set -uo pipefail

STAGE="$1";  PREFIX="$2"; SERVICES_RAW="$3"; HEALTH_RAW="$4"
VERSION="$5"; NO_RESTART="$6"
shift 6
CMDS=("$@")

read -ra SERVICES <<< "$SERVICES_RAW"

say() { printf '    [remote] %s\n' "$*"; }

# health_for prints the URL configured for a unit, or nothing.
health_for() {
    local unit="$1" pair
    for pair in $HEALTH_RAW; do
        if [[ "$pair" == "$unit="* ]]; then
            printf '%s' "${pair#*=}"
            return
        fi
    done
}

# Atomic install. A running binary cannot be overwritten in place (ETXTBSY), so
# write alongside and mv -- which is atomic within one filesystem, so the path is
# never missing or half-written. Keep .prev for rollback.
for cmd in "${CMDS[@]}"; do
    if [[ -f "$PREFIX/$cmd" ]]; then
        cp -p "$PREFIX/$cmd" "$PREFIX/$cmd.prev"
    fi
    install -m 0755 "$STAGE/$cmd" "$PREFIX/$cmd.new"
    mv -f "$PREFIX/$cmd.new" "$PREFIX/$cmd"
    say "installed $cmd"
done

printf '%s\n' "$VERSION" > "$PREFIX/.sonyliv-deployed-version"
rm -rf "$STAGE"

# Rollback restores every binary and restarts every unit that was present, not
# just the one that failed. The binaries are shared, so a unit that restarted
# happily is now running code that has just been withdrawn.
rollback() {
    say "ROLLING BACK"
    for cmd in "${CMDS[@]}"; do
        if [[ -f "$PREFIX/$cmd.prev" ]]; then
            mv -f "$PREFIX/$cmd.prev" "$PREFIX/$cmd"
            say "restored $cmd"
        else
            say "no previous $cmd to restore (first deploy)"
        fi
    done
    local unit
    for unit in "${PRESENT[@]:-}"; do
        [[ -n "$unit" ]] && systemctl restart "$unit" 2>/dev/null || true
    done
}

if [[ "$NO_RESTART" == "1" ]]; then
    say "--no-restart: leaving ${SERVICES[*]} untouched"
    exit 0
fi

# Only restart what actually exists. A missing unit is the expected path on a box
# that runs a subset of the services, not an error.
PRESENT=()
for unit in "${SERVICES[@]}"; do
    if systemctl list-unit-files "$unit.service" --no-legend 2>/dev/null | grep -q .; then
        PRESENT+=("$unit")
    else
        say "unit $unit.service is not installed; skipping"
    fi
done
if [[ ${#PRESENT[@]} -eq 0 ]]; then
    say "no units installed; binaries in place, nothing restarted"
    exit 0
fi

systemctl daemon-reload

for unit in "${PRESENT[@]}"; do
    systemctl restart "$unit" || { say "$unit restart failed"; rollback; exit 4; }

    # Wait for the unit to settle. Restart=always means a crash-looping service
    # can report active briefly, so require it to hold.
    for _ in $(seq 1 15); do
        sleep 1
        systemctl is-active --quiet "$unit" || continue
        break
    done
    if ! systemctl is-active --quiet "$unit"; then
        say "$unit did not stay active"
        systemctl --no-pager --lines=20 status "$unit" || true
        rollback
        exit 4
    fi
    say "$unit active"

    # Health check from ON the box, so no security-group change is needed and we
    # are not testing a load balancer by accident.
    url="$(health_for "$unit")"
    if [[ -z "$url" ]]; then
        say "$unit: no health url configured, skipping check"
        continue
    fi
    ok=0
    for i in $(seq 1 30); do
        if curl -fsSk --max-time 2 "$url" >/dev/null 2>&1; then
            say "$unit health ok after ${i}s"
            ok=1
            break
        fi
        sleep 1
    done
    if [[ "$ok" != "1" ]]; then
        say "$unit health check failed: $url"
        journalctl -u "$unit" --no-pager --lines=30 || true
        rollback
        exit 4
    fi
done
REMOTE
rc=$?
set -e

case "$rc" in
    0) log "deployed ${VERSION}" ;;
    4) die "service did not come up; binaries were rolled back" 4 ;;
    *) die "remote install failed (exit $rc)" 3 ;;
esac
