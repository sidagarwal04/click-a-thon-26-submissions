"""Export a Langfuse trace to committed JSON.

WHY THIS EXISTS
---------------
Our Langfuse runs on a private VM reachable only over Tailscale, so the
trace_url written into diagnosis.json — and Langfuse's own "share" links, which
are just unauthenticated URLs on the same host — are unreachable to anyone
outside the tailnet. The InMobi guidelines accept "shared *or exported* traces",
and "no trace, no credit" applies to the unseen incident, so exporting is not a
convenience: it is the only form of the evidence a reader outside our network
can actually open.

Writes the full trace with every observation, so a reader can follow what was
checked, in what order, and why — including the branches that were ruled out.

    python scripts/export_trace.py out/diagnosis.json artifacts/traces/
"""
import base64
import json
import os
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from engine.db import _load_env  # noqa: E402


def fetch(host: str, auth: str, path: str) -> dict:
    req = urllib.request.Request(f"{host}{path}", headers={"Authorization": f"Basic {auth}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


# Langfuse stamps the ingesting client's public key into every observation's
# metadata. It is the publishable half of the pair and useless without the
# secret, but this export is committed to a public repository, so it is scrubbed
# rather than reasoned about: a credential in git history is permanent, and
# "it's only the public one" is exactly the argument that precedes an incident.
SCRUB_KEYS = {"public_key", "publicKey", "secret_key", "secretKey",
              "api_key", "apiKey", "authorization", "password"}


def scrub(obj):
    if isinstance(obj, dict):
        return {k: ("<redacted>" if k in SCRUB_KEYS else scrub(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [scrub(v) for v in obj]
    return obj


def summarise(trace: dict) -> str:
    obs = trace.get("observations") or []
    L = [
        f"# Trace — {trace.get('name', 'investigation')}",
        "",
        f"**Trace ID:** `{trace.get('id')}`  ",
        f"**Started:** {trace.get('timestamp')}  ",
        f"**Observations:** {len(obs)}",
        "",
        "Our Langfuse instance runs on a private VM, so the in-app link is not",
        "reachable from outside our network. This is the full export — every span,",
        "in order, with its input, output and timing. It is the same object the",
        "Langfuse UI renders.",
        "",
        "The trace records *what was checked, in what order, and with what verdict*.",
        "The SQL behind every number is in `queries.md` alongside it, not in the span.",
        "",
        "## Stages, in execution order",
        "",
        "| Stage | Type | Duration | Note |",
        "|---|---|---:|---|",
    ]
    for o in sorted(obs, key=lambda x: x.get("startTime") or ""):
        start, end = o.get("startTime"), o.get("endTime")
        dur = ""
        if start and end:
            from datetime import datetime
            try:
                fmt = lambda s: datetime.fromisoformat(s.replace("Z", "+00:00"))
                dur = f"{(fmt(end) - fmt(start)).total_seconds():.2f}s"
            except Exception:  # noqa: BLE001
                dur = ""
        out = o.get("output")
        note = ""
        if isinstance(out, dict):
            for k in ("verdict", "classification", "responsible", "novel_compound_findings",
                      "events", "hours_flagged"):
                if k in out:
                    note = f"`{k}` present"
                    break
        L.append(f"| `{o.get('name')}` | {o.get('type')} | {dur} | {note} |")
    L += ["", "The ruled-out branches appear here alongside the winning one — a stage that",
          "cleared a dimension is recorded with the numbers that cleared it, not dropped.", ""]
    return "\n".join(L)


def main() -> int:
    src = Path(sys.argv[1] if len(sys.argv) > 1 else "out/diagnosis.json")
    dst = Path(sys.argv[2] if len(sys.argv) > 2 else "artifacts/traces")
    dst.mkdir(parents=True, exist_ok=True)

    _load_env()
    host = (os.getenv("LANGFUSE_HOST") or "").rstrip("/")
    pk, sk = os.getenv("LANGFUSE_PUBLIC_KEY"), os.getenv("LANGFUSE_SECRET_KEY")
    if not (host and pk and sk):
        print("LANGFUSE_HOST / PUBLIC_KEY / SECRET_KEY not set — cannot export", file=sys.stderr)
        return 1

    url = json.loads(src.read_text()).get("trace_url")
    if not url:
        print("no trace_url in diagnosis — was the run traced?", file=sys.stderr)
        return 1
    tid = url.rstrip("/").rsplit("/", 1)[-1]

    auth = base64.b64encode(f"{pk}:{sk}".encode()).decode()
    trace = fetch(host, auth, f"/api/public/traces/{tid}")

    trace = scrub(trace)
    (dst / f"{tid}.json").write_text(json.dumps(trace, indent=2, sort_keys=True))
    (dst / f"{tid}.md").write_text(summarise(trace))
    print(f"exported {len(trace.get('observations') or [])} observations -> {dst}/{tid}.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
