#!/usr/bin/env bash
# One-click deploy, from a BARE machine, with preflight + postflight checks.
#
# Design goal: NEVER leave the user staring at a stack trace or a silently
# half-broken stack. Every failure mode we've actually hit during this build
# is checked for explicitly and reported with the fix, before or after the
# containers come up:
#   - Docker not installed at all (a fresh EC2 AMI has nothing)
#   - Docker installed but the daemon not running
#   - the compose v2 plugin missing (this script uses `docker compose`, not
#     the legacy `docker-compose` binary)
#   - utils/.env missing or missing credentials
#   - host port already taken by an unrelated process (this bit us on :8000 --
#     compose reported the container "healthy" while publishing nothing)
#   - a container that starts and then immediately crash-loops
#   - API up but UI or the nginx->API proxy broken
#
# WHAT IT INSTALLS, AND WHAT IT DELIBERATELY DOES NOT
# Docker, the compose plugin and curl -- that is the entire runtime dependency
# list, because ClickHouse is external (ClickHouse Cloud, via utils/.env) and
# all four services build from the two Dockerfiles in this repo. Python is NOT
# installed: the containers carry their own, and the helper scripts under
# scripts/ are an operator convenience rather than part of the deploy.
#
# utils/.env is never created or guessed. It holds credentials, and a deploy
# script that invents a config file produces a stack that starts and is wrong.
#
# Usage:
#   ./scripts/deploy.sh                # install anything missing, then deploy
#   ./scripts/deploy.sh --no-install   # never touch the system; report and exit
set -uo pipefail
cd "$(dirname "$0")/.."  # repo root -- compose file and utils/.env live there

API_PORT=8088
UI_PORT=80
FAILED=0
NO_INSTALL=0
# Every docker call goes through this. It becomes "sudo docker" when the daemon
# is only reachable as root -- see the group-membership note in ensure_docker.
DOCKER="docker"

for arg in "$@"; do
  case "$arg" in
    --no-install) NO_INSTALL=1 ;;
    -h|--help) sed -n '2,30p' "$0"; exit 0 ;;
    *) printf 'Unknown argument: %s (try --help)\n' "$arg"; exit 2 ;;
  esac
done

say()  { printf '%s\n' "$*"; }
ok()   { printf '  [ OK ] %s\n' "$*"; }
warn() { printf '  [WARN] %s\n' "$*"; }
bad()  { printf '  [FAIL] %s\n' "$*"; FAILED=1; }
step() { printf '  [ .. ] %s\n' "$*"; }

# ------------------------------------------------------------------ platform
# ID and ID_LIKE from os-release. Used only to pick a package manager -- never
# to assume a package is present.
OS_ID=""; OS_LIKE=""; OS_NAME="unknown"
if [ -r /etc/os-release ]; then
  # shellcheck disable=SC1091
  . /etc/os-release
  OS_ID="${ID:-}"; OS_LIKE="${ID_LIKE:-}"; OS_NAME="${PRETTY_NAME:-$OS_ID}"
fi

# dnf | apt | "" (unknown -- we refuse to guess)
pkg_family() {
  case "$OS_ID" in
    amzn|fedora|rhel|centos|rocky|almalinux) echo dnf; return ;;
    debian|ubuntu) echo apt; return ;;
  esac
  case "$OS_LIKE" in
    *rhel*|*fedora*) echo dnf; return ;;
    *debian*) echo apt; return ;;
  esac
  echo ""
}
PKG=$(pkg_family)

SUDO=""
if [ "$(id -u)" -eq 0 ]; then
  SUDO=""
elif command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null; then
  SUDO="sudo"
elif command -v sudo >/dev/null 2>&1; then
  # sudo exists but wants a password -- still usable, it will prompt.
  SUDO="sudo"
fi

can_install() {
  [ "$NO_INSTALL" -eq 0 ] && [ -n "$PKG" ] && { [ "$(id -u)" -eq 0 ] || [ -n "$SUDO" ]; }
}

# Prints the manual commands for this platform, so a refusal is still actionable.
manual_docker_instructions() {
  case "$PKG" in
    dnf)
      say "        sudo dnf install -y docker docker-compose-plugin"
      say "        sudo systemctl enable --now docker"
      say "        sudo usermod -aG docker \"\$USER\"   # then log out and back in" ;;
    apt)
      say "        curl -fsSL https://get.docker.com | sudo sh"
      say "        sudo usermod -aG docker \"\$USER\"   # then log out and back in" ;;
    *)
      say "        Detected OS: $OS_NAME (no known package manager)."
      say "        Install Docker Engine + the compose v2 plugin manually:"
      say "        https://docs.docker.com/engine/install/" ;;
  esac
}

pkg_install() {  # $1.. = package names
  case "$PKG" in
    dnf) $SUDO dnf install -y "$@" >/dev/null 2>&1 ;;
    apt) DEBIAN_FRONTEND=noninteractive $SUDO apt-get install -y "$@" >/dev/null 2>&1 ;;
    *)   return 1 ;;
  esac
}

# ----------------------------------------------------------- ensure: curl
ensure_curl() {
  if command -v curl >/dev/null 2>&1; then
    ok "curl available (needed for postflight health checks)"
    return
  fi
  if ! can_install; then
    bad "curl not found on PATH -- postflight cannot verify the API/UI."
    say "        Install it: ${PKG:-your package manager} install curl"
    return
  fi
  step "curl missing -- installing"
  [ "$PKG" = apt ] && $SUDO apt-get update -qq >/dev/null 2>&1
  if pkg_install curl && command -v curl >/dev/null 2>&1; then
    ok "curl installed"
  else
    bad "curl could not be installed automatically."
  fi
}

# ----------------------------------------------------------- ensure: docker
install_docker() {
  case "$PKG" in
    dnf)
      step "installing Docker via dnf ($OS_NAME)"
      # Amazon Linux 2023 ships docker in its own repo; the compose plugin is
      # packaged separately and is absent on some minor versions, so its
      # failure is not fatal here -- ensure_compose falls back to a direct
      # plugin download.
      pkg_install docker || return 1
      pkg_install docker-compose-plugin || true
      ;;
    apt)
      step "installing Docker via get.docker.com ($OS_NAME)"
      # The convenience script, not distro packages: Ubuntu's own docker.io is
      # frequently too old to ship compose v2, and this pulls the official repo
      # plus the compose plugin in one step.
      $SUDO apt-get update -qq >/dev/null 2>&1
      pkg_install ca-certificates curl >/dev/null 2>&1 || true
      curl -fsSL https://get.docker.com -o /tmp/get-docker.sh 2>/dev/null || return 1
      $SUDO sh /tmp/get-docker.sh >/dev/null 2>&1 || return 1
      ;;
    *) return 1 ;;
  esac
  $SUDO systemctl enable --now docker >/dev/null 2>&1 || true
  # Lets future shells run docker without sudo. Does NOT affect THIS shell --
  # group membership is fixed at login -- which is what the sudo fallback in
  # ensure_docker exists to bridge.
  [ "$(id -u)" -ne 0 ] && $SUDO usermod -aG docker "$(id -un)" >/dev/null 2>&1 || true
  return 0
}

ensure_docker() {
  if ! command -v docker >/dev/null 2>&1; then
    if ! can_install; then
      if [ "$NO_INSTALL" -eq 1 ]; then
        bad "docker not found on PATH, and --no-install was given."
      else
        bad "docker not found on PATH, and it cannot be installed automatically here."
      fi
      manual_docker_instructions
      return
    fi
    if ! install_docker; then
      bad "Docker installation failed on $OS_NAME. Install it manually:"
      manual_docker_instructions
      return
    fi
    ok "Docker installed ($OS_NAME)"
  fi

  # Daemon reachable? Try unprivileged first, then as root. The second case is
  # the normal state immediately after a fresh install: usermod -aG docker has
  # run but this shell predates it, so the socket is root-only until re-login.
  if $DOCKER info >/dev/null 2>&1; then
    ok "Docker daemon responding"
    return
  fi
  if [ -n "$SUDO" ] && $SUDO docker info >/dev/null 2>&1; then
    DOCKER="$SUDO docker"
    ok "Docker daemon responding (via sudo)"
    warn "Your user is not in the 'docker' group yet -- log out and back in to drop the sudo. Continuing with sudo for this run."
    return
  fi
  # Installed but dead: try to start it before giving up.
  if [ -n "$SUDO" ]; then
    step "Docker daemon not responding -- starting it"
    $SUDO systemctl enable --now docker >/dev/null 2>&1 || true
    sleep 3
    if $DOCKER info >/dev/null 2>&1; then ok "Docker daemon responding"; return; fi
    if $SUDO docker info >/dev/null 2>&1; then
      DOCKER="$SUDO docker"; ok "Docker daemon responding (via sudo)"; return
    fi
  fi
  bad "Docker is installed but the daemon is not responding. Try: sudo systemctl status docker"
}

# ------------------------------------------------- ensure: compose v2 plugin
ensure_compose() {
  # Nothing useful to say when docker itself is missing: the instructions
  # printed by ensure_docker already install the plugin, so reporting it
  # separately is a second failure for one cause.
  if ! command -v docker >/dev/null 2>&1; then
    return
  fi
  if $DOCKER compose version >/dev/null 2>&1; then
    ok "docker compose v2 available ($($DOCKER compose version --short 2>/dev/null))"
    return
  fi
  if ! can_install; then
    bad "the 'docker compose' v2 plugin is missing (this script does not use legacy docker-compose)."
    say "        Install it: https://docs.docker.com/compose/install/linux/"
    return
  fi
  step "docker compose plugin missing -- installing"
  pkg_install docker-compose-plugin || true
  if $DOCKER compose version >/dev/null 2>&1; then
    ok "docker compose v2 installed"
    return
  fi
  # Distro package unavailable (happens on some AL2023 minor versions): drop the
  # official plugin binary straight into the CLI plugin directory.
  local arch dest
  arch=$(uname -m)
  dest=/usr/libexec/docker/cli-plugins
  $SUDO mkdir -p "$dest" 2>/dev/null
  if curl -fsSL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-${arch}" \
       -o /tmp/docker-compose 2>/dev/null; then
    $SUDO install -m 0755 /tmp/docker-compose "$dest/docker-compose" 2>/dev/null
  fi
  if $DOCKER compose version >/dev/null 2>&1; then
    ok "docker compose v2 installed (plugin binary)"
  else
    bad "could not install the docker compose v2 plugin automatically."
    say "        https://docs.docker.com/compose/install/linux/"
  fi
}

# ------------------------------------------------------------- port checking
# ss first (iproute2, present on every current AMI), netstat as a fallback.
# If NEITHER exists the check is reported as SKIPPED, never as "free": the old
# version returned "not busy" when netstat was missing, so on exactly the bare
# machine this script exists to bootstrap, the port check silently always passed.
PORT_TOOL=""
detect_port_tool() {
  if command -v ss >/dev/null 2>&1; then PORT_TOOL="ss"
  elif command -v netstat >/dev/null 2>&1; then PORT_TOOL="netstat"
  else PORT_TOOL=""
  fi
}
detect_port_tool

# Installed rather than merely warned about: this host is already being
# provisioned, and a port check that cannot run is a check that finds nothing.
# Package name differs -- iproute2 on Debian/Ubuntu, iproute on the RHEL family.
ensure_port_tool() {
  [ -n "$PORT_TOOL" ] && return
  can_install || return
  step "neither ss nor netstat found -- installing iproute"
  case "$PKG" in
    apt) $SUDO apt-get update -qq >/dev/null 2>&1; pkg_install iproute2 ;;
    dnf) pkg_install iproute ;;
  esac
  detect_port_tool
  [ -n "$PORT_TOOL" ] && ok "$PORT_TOOL installed (port conflict check enabled)"
}

port_busy() {  # $1 = port. Returns 0 if something is listening.
  case "$PORT_TOOL" in
    # No -H: the flag is newer than some iproute2 builds, and the header line
    # cannot match a ":<port> " pattern anyway.
    ss)      ss -ltn 2>/dev/null | grep -qE "[:.]$1[[:space:]]" ;;
    netstat) netstat -ano 2>/dev/null | grep -E "[:.]$1[[:space:]]" | grep -qi "LISTENING\|LISTEN" ;;
    *)       return 2 ;;   # unknown, NOT "free"
  esac
}

# $1 = key name. Echoes the trimmed value (leading/trailing whitespace and CR
# removed) so "KEY=   " reads as empty -- matching deploy.ps1's
# IsNullOrWhiteSpace check, which would otherwise disagree across platforms.
env_value() {
  grep -E "^$1=" utils/.env 2>/dev/null | head -1 | cut -d= -f2- \
    | tr -d '\r' | sed 's/^[[:space:]]*//; s/[[:space:]]*$//'
}

# ----------------------------------------------------------------- preflight
say "== Preflight =="
say "  host: $OS_NAME"

ensure_docker
ensure_compose
ensure_curl
ensure_port_tool

[ -f docker-compose.yml ] && ok "docker-compose.yml found" || bad "docker-compose.yml not found (are you in the right repo?)"

if [ ! -f utils/.env ]; then
  bad "utils/.env not found. Run: cp utils/.env.example utils/.env  then fill in your credentials."
else
  ok "utils/.env found"
  # Required to boot at all. Missing LLM/Langfuse keys are only a WARNING --
  # the system is designed to degrade safely without them.
  for required in CLICKHOUSE_HOST CLICKHOUSE_PASSWORD CLICKHOUSE_DATABASE; do
    val=$(env_value "$required")
    [ -n "$val" ] && ok "$required is set" || bad "$required is empty in utils/.env -- ClickHouse queries will fail."
  done
  for optional in GEMINI_API_KEY LANGFUSE_PUBLIC_KEY LANGFUSE_SECRET_KEY; do
    val=$(env_value "$optional")
    [ -n "$val" ] && ok "$optional is set" \
                  || warn "$optional is empty -- deploy continues, but that feature degrades (run scripts/check_keys.py for detail)."
  done
fi

# Only a problem if it's NOT our own already-running stack. Match against the
# PORTS column's "0.0.0.0:8088->8000/tcp" form -- NOT '{{.Publishers}}', whose
# output is space-separated ("{0.0.0.0 8000 8088 tcp}") so a ":8088" grep
# silently never matches and every re-deploy looks like a port conflict.
for p in $API_PORT $UI_PORT; do
  port_busy "$p"; rc=$?
  if [ "$rc" -eq 0 ]; then
    if $DOCKER compose ps 2>/dev/null | grep -q ":${p}->"; then
      ok "port $p held by this project's own container (will be recreated)"
    else
      bad "port $p is already taken by another process. Free it, or change the mapping in docker-compose.yml AND this script."
    fi
  elif [ "$rc" -eq 2 ]; then
    warn "port $p NOT CHECKED -- neither ss nor netstat is available on this host."
  else
    ok "port $p free"
  fi
done

if [ "$FAILED" -ne 0 ]; then
  say ""
  say "Preflight failed -- nothing was started. Fix the [FAIL] items above and re-run."
  exit 1
fi

# -------------------------------------------------------------------- deploy
say ""
say "== Building and starting (api, scanner, scanner-unseen, ui) =="
if ! $DOCKER compose up --build -d; then
  say ""
  say "docker compose failed to start. Recent logs:"
  $DOCKER compose logs --tail=40 2>&1 | sed 's/^/    /'
  exit 1
fi

# ---------------------------------------------------------------- postflight
say ""
say "== Postflight =="

printf '  waiting for API'
API_UP=0
for _ in $(seq 1 30); do
  if curl -sf "http://127.0.0.1:$API_PORT/healthz" >/dev/null 2>&1; then API_UP=1; break; fi
  printf '.'
  sleep 2
done
printf '\n'
[ "$API_UP" -eq 1 ] && ok "API healthy      http://127.0.0.1:$API_PORT/healthz" \
                    || bad "API never became healthy on port $API_PORT"

printf '  waiting for UI'
UI_UP=0
for _ in $(seq 1 15); do
  if curl -sf "http://127.0.0.1:$UI_PORT/" >/dev/null 2>&1; then UI_UP=1; break; fi
  printf '.'
  sleep 2
done
printf '\n'
[ "$UI_UP" -eq 1 ] && ok "UI serving       http://127.0.0.1:$UI_PORT" \
                   || bad "UI not reachable on port $UI_PORT"

# The UI is useless if nginx can't reach the API, and that failure is
# invisible from either container's own health check.
if curl -sf "http://127.0.0.1:$UI_PORT/api/metrics" >/dev/null 2>&1; then
  ok "UI -> API proxy working"
else
  bad "UI is up but cannot reach the API through nginx (check ui/nginx.conf proxy_pass)."
fi

# A crash-looping container still counts as "started" to compose, so check
# actual current state rather than trusting the up command's exit code.
for svc in api scanner scanner-unseen ui; do
  state=$($DOCKER compose ps --status running --services 2>/dev/null | grep -x "$svc" || true)
  if [ -n "$state" ]; then
    ok "container '$svc' running"
  else
    bad "container '$svc' is NOT running -- last 20 log lines:"
    $DOCKER compose logs --tail=20 "$svc" 2>&1 | sed 's/^/        /'
  fi
done

say ""
if [ "$FAILED" -ne 0 ]; then
  say "Deploy finished with problems (see [FAIL] above). Full logs: $DOCKER compose logs -f"
  exit 1
fi

# EC2 IMDSv2. Short timeouts and a silent skip, so this costs nothing and says
# nothing when the script is run anywhere else.
PUBLIC_IP=""
if TOKEN=$(curl -sf -X PUT "http://169.254.169.254/latest/api/token" \
      -H "X-aws-ec2-metadata-token-ttl-seconds: 60" --max-time 1 2>/dev/null); then
  PUBLIC_IP=$(curl -sf -H "X-aws-ec2-metadata-token: $TOKEN" \
      "http://169.254.169.254/latest/meta-data/public-ipv4" --max-time 1 2>/dev/null)
fi

say "Ready:"
if [ -n "$PUBLIC_IP" ]; then
  say "  UI:  http://$PUBLIC_IP:$UI_PORT      (local: http://127.0.0.1:$UI_PORT)"
  say "  API: http://$PUBLIC_IP:$API_PORT      (local: http://127.0.0.1:$API_PORT)"
else
  say "  UI:  http://127.0.0.1:$UI_PORT"
  say "  API: http://127.0.0.1:$API_PORT"
fi
say ""
# Stated every run, not just on EC2. The console has no login and the API sets
# allow_origins=["*"] -- on a public host the security group is the ONLY thing
# between this and the internet, and that is worth saying out loud rather than
# leaving to be discovered.
say "  [WARN] This stack has NO AUTHENTICATION. Ports $API_PORT and $UI_PORT are published on"
say "         0.0.0.0, so anything your firewall or EC2 security group allows can reach it."
say "         Restrict inbound $API_PORT/$UI_PORT to your own IP before leaving it running."
say ""
if [ -x .venv/bin/python ]; then
  say "  Config check: .venv/bin/python scripts/check_keys.py"
else
  say "  Config check: $DOCKER compose exec api python scripts/check_keys.py"
fi
say "  Logs:         $DOCKER compose logs -f"
say "  Stop:         $DOCKER compose down"
