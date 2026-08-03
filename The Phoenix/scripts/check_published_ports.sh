#!/usr/bin/env bash
# THE DEPLOYMENT CLAIM, AS A TEST.
#
# Two header comments assert that port 80 is the only thing this host exposes. Both were false: an
# `include:` of the vendored LibreChat compose file published 3080 and 3000 on 0.0.0.0. A comment
# cannot notice that; this can.
#
# Loopback bindings are allowed: 127.0.0.1:3080 is reachable from the host for debugging and from
# nowhere else. What is forbidden is a mapping with no host IP, or one bound to 0.0.0.0.
set -euo pipefail
cd "$(dirname "$0")/.."

bad="$(docker compose config --format json 2>/dev/null \
  | python3 -c '
import json, sys
cfg = json.load(sys.stdin)
out = []
for name, svc in (cfg.get("services") or {}).items():
    for p in (svc.get("ports") or []):
        published, host_ip = str(p.get("published", "")), p.get("host_ip", "")
        if not published:
            continue
        if published == "80" and host_ip in ("", "0.0.0.0"):
            continue                       # the one intended public port
        if host_ip in ("127.0.0.1", "::1"):
            continue                       # loopback only, not exposed
        shown = host_ip or "0.0.0.0"
        out.append(name + "\t" + shown + ":" + published)
print("\n".join(out))
')"

if [ -n "$bad" ]; then
  echo "FAIL: ports published beyond 80" >&2
  echo "$bad" >&2
  echo "Bind them to 127.0.0.1 in docker-compose.override.yml, or use expose: instead of ports:" >&2
  exit 1
fi
echo "ok: port 80 is the only publicly published port"
