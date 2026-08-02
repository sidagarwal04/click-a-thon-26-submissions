# One-click demo deploy with preflight + postflight checks (WINDOWS ONLY).
#
# Docker Desktop is the Windows product; on Linux the equivalent is Docker
# Engine and there is no Desktop at all -- scripts/deploy.sh installs Engine
# itself (dnf on Amazon Linux, get.docker.com on Ubuntu/Debian) and never
# mentions Desktop. Use that script on EC2; use this one on a Windows box.
#
# This script deliberately does NOT auto-install: Docker Desktop needs WSL2 and
# a reboot, so an install started here could not finish in the same run, and it
# carries licensing terms a deploy script has no business accepting for you.
#
# Mirrors scripts/deploy.sh's checks, in the same order, so the two outputs can
# be diffed side by side. Design goal: NEVER leave the user staring
# at a stack trace or a silently half-broken stack. Every failure mode we
# actually hit during this build is checked explicitly and reported with the
# fix: Docker not running, missing utils/.env or credentials, a host port
# already taken by an unrelated process (this bit us on :8000 -- compose
# reported the container "healthy" while publishing nothing), a container that
# starts then crash-loops, and API-up-but-UI-or-proxy-broken.

Set-Location (Split-Path $PSScriptRoot -Parent)  # repo root

$ApiPort = 8088
$UiPort  = 80
$script:Failed = $false

function Say  ($m) { Write-Host $m }
function Ok   ($m) { Write-Host "  [ OK ] $m" }
function Warn ($m) { Write-Host "  [WARN] $m" -ForegroundColor Yellow }
function Bad  ($m) { Write-Host "  [FAIL] $m" -ForegroundColor Red; $script:Failed = $true }

function Test-PortBusy ($Port) {
    $c = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    return $null -ne $c
}

function Get-EnvValue ($Name) {
    if (-not (Test-Path "utils/.env")) { return "" }
    $line = Select-String -Path "utils/.env" -Pattern "^$Name=" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -eq $line) { return "" }
    return ($line.Line -replace "^$Name=", "").Trim()
}

# ----------------------------------------------------------------- preflight
Say "== Preflight =="

$dockerOk = $false
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Bad "docker not found on PATH."
    Say "        Install Docker Desktop (Windows):"
    Say "          winget install -e --id Docker.DockerDesktop"
    Say ""
    Say "        Requires WSL2 and a reboot. After installing, start Docker"
    Say "        Desktop and wait for the whale icon to stop animating, then"
    Say "        re-run this script."
} else {
    docker info *>$null
    if ($LASTEXITCODE -eq 0) { Ok "Docker daemon responding"; $dockerOk = $true }
    else { Bad "Docker daemon is not responding. Start Docker Desktop, wait for the whale icon to stop animating, then re-run." }
}

# Parity with deploy.sh's ensure_compose. This script uses `docker compose`
# throughout, so a machine carrying only the legacy `docker-compose` binary
# would fail at the build step with a confusing error instead of here.
if ($dockerOk) {
    $composeVer = (docker compose version --short 2>$null)
    if ($LASTEXITCODE -eq 0 -and $composeVer) { Ok "docker compose v2 available ($composeVer)" }
    else { Bad "the 'docker compose' v2 plugin is missing. Docker Desktop ships it -- update Docker Desktop." }
}

# Parity with deploy.sh's curl guard. PowerShell uses Invoke-WebRequest, which
# ships with the shell, so this can never fail -- reported anyway so both
# scripts emit the same line in the same position.
Ok "Invoke-WebRequest available (needed for postflight health checks)"

if (Test-Path "docker-compose.yml") { Ok "docker-compose.yml found" }
else { Bad "docker-compose.yml not found (are you in the right repo?)" }

if (-not (Test-Path "utils/.env")) {
    Bad "utils/.env not found. Run: Copy-Item utils/.env.example utils/.env  then fill in your credentials."
} else {
    Ok "utils/.env found"
    # Required to boot at all.
    foreach ($k in @("CLICKHOUSE_HOST", "CLICKHOUSE_PASSWORD", "CLICKHOUSE_DATABASE")) {
        if ([string]::IsNullOrWhiteSpace((Get-EnvValue $k))) { Bad "$k is empty in utils/.env -- ClickHouse queries will fail." }
        else { Ok "$k is set" }
    }
    # Optional: the system degrades safely without these, so warn only.
    foreach ($k in @("GEMINI_API_KEY", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY")) {
        if ([string]::IsNullOrWhiteSpace((Get-EnvValue $k))) {
            Warn "$k is empty -- deploy continues, but that feature degrades (run scripts/check_keys.py for detail)."
        } else { Ok "$k is set" }
    }
}

# Runs unconditionally (not gated on Docker) so the output matches deploy.sh
# even when the daemon is down -- a port conflict is worth reporting in the
# same run as the Docker failure, not hidden behind it.
# Match the PORTS column's "0.0.0.0:8088->8000/tcp" form -- NOT
# '{{.Publishers}}', whose output is space-separated ("{0.0.0.0 8000 8088 tcp}")
# so a ":8088" match silently never fires and every re-deploy looks like a
# port conflict.
$ourPorts = if ($dockerOk) { (docker compose ps 2>$null) -join "`n" } else { "" }
foreach ($p in @($ApiPort, $UiPort)) {
    if (Test-PortBusy $p) {
        if ($ourPorts -match ":$p->") { Ok "port $p held by this project's own container (will be recreated)" }
        else { Bad "port $p is already taken by another process. Free it, or change the mapping in docker-compose.yml AND this script." }
    } else { Ok "port $p free" }
}

if ($script:Failed) {
    Say ""
    Say "Preflight failed -- nothing was started. Fix the [FAIL] items above and re-run."
    exit 1
}

# -------------------------------------------------------------------- deploy
Say ""
Say "== Building and starting (api, scanner, scanner-unseen, ui) =="
docker compose up --build -d
if ($LASTEXITCODE -ne 0) {
    Say ""
    Say "docker compose failed to start. Recent logs:"
    docker compose logs --tail=40 | ForEach-Object { Write-Host ("    " + $_) }
    exit 1
}

# ---------------------------------------------------------------- postflight
Say ""
Say "== Postflight =="

function Wait-Url ($Url, $Attempts) {
    for ($i = 0; $i -lt $Attempts; $i++) {
        try {
            $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
            if ($r.StatusCode -eq 200) { return $true }
        } catch {}
        Write-Host "." -NoNewline
        Start-Sleep -Seconds 2
    }
    return $false
}

Write-Host "  waiting for API" -NoNewline
if (Wait-Url "http://127.0.0.1:$ApiPort/healthz" 30) { Write-Host ""; Ok "API healthy      http://127.0.0.1:$ApiPort/healthz" }
else { Write-Host ""; Bad "API never became healthy on port $ApiPort" }

Write-Host "  waiting for UI" -NoNewline
if (Wait-Url "http://127.0.0.1:$UiPort/" 15) { Write-Host ""; Ok "UI serving       http://127.0.0.1:$UiPort" }
else { Write-Host ""; Bad "UI not reachable on port $UiPort" }

# The UI is useless if nginx can't reach the API, and that failure is
# invisible from either container's own health check.
try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:$UiPort/api/metrics" -UseBasicParsing -TimeoutSec 5
    if ($r.StatusCode -eq 200) { Ok "UI -> API proxy working" } else { Bad "UI -> API proxy returned $($r.StatusCode)" }
} catch {
    Bad "UI is up but cannot reach the API through nginx (check ui/nginx.conf proxy_pass)."
}

# A crash-looping container still counts as "started" to compose, so check
# actual current state rather than trusting the up command's exit code.
$running = (docker compose ps --status running --services 2>$null)
foreach ($svc in @("api", "scanner", "scanner-unseen", "ui")) {
    if ($running -contains $svc) { Ok "container '$svc' running" }
    else {
        Bad "container '$svc' is NOT running -- last 20 log lines:"
        docker compose logs --tail=20 $svc | ForEach-Object { Write-Host ("        " + $_) }
    }
}

Say ""
if ($script:Failed) {
    Say "Deploy finished with problems (see [FAIL] above). Full logs: docker compose logs -f"
    exit 1
}

Say "Ready:"
Say "  UI:  http://127.0.0.1:$UiPort"
Say "  API: http://127.0.0.1:$ApiPort"
Say ""
# Stated every run, same as deploy.sh. The console has no login and the API
# sets allow_origins=["*"]; on any reachable host the firewall is the only
# thing in front of it, and that is worth saying rather than leaving to be
# discovered.
Warn "This stack has NO AUTHENTICATION. Ports $ApiPort and $UiPort are published on 0.0.0.0,"
Say  "         so anything your firewall allows can reach it. Restrict inbound"
Say  "         $ApiPort/$UiPort before leaving it running."
Say ""
if (Test-Path ".venv/Scripts/python.exe") {
    Say "  Config check: .venv\Scripts\python.exe scripts/check_keys.py"
} else {
    Say "  Config check: docker compose exec api python scripts/check_keys.py"
}
Say "  Logs:         docker compose logs -f"
Say "  Stop:         docker compose down"
