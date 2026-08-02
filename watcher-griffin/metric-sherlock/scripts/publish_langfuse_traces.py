"""Publishes every Langfuse trace in the project, so any judge can open one from a link.

WHY THIS EXISTS ALONGSIDE THE CODE CHANGE
`engine/tracing.py` now publishes each trace as it is created, which covers everything from
this point on. It cannot cover what already happened: traces written before that change are
private, and "no trace, no credit" applies to the runs already sitting in the project. This
backfills them.

HOW IT WORKS
Langfuse's ingestion endpoint upserts a trace by id, so sending `{"id": <existing>, "public":
true}` flips the flag on a trace that already exists without touching anything else. Verified
on a real trace before this was written: 73 observations and the trace name survived the
upsert unchanged, and only `public` moved.

Ingestion is asynchronous -- the API returns 201 immediately and the flag appears roughly ten
to twenty seconds later -- so `--verify` polls rather than reading back straight away.

IRREVERSIBLE, AND PUBLIC TO THE INTERNET. Publication cannot be undone programmatically. Every
published trace exposes its full contents (verbatim ClickHouse SQL, the evidence bundle, LLM
prompts and replies) to anyone holding the URL, with no login. That is acceptable here because
this dataset is synthetic. Do not run this against a project carrying real data.

Usage:
    .venv/Scripts/python.exe scripts/publish_langfuse_traces.py            # publish all
    .venv/Scripts/python.exe scripts/publish_langfuse_traces.py --dry-run  # report only
    .venv/Scripts/python.exe scripts/publish_langfuse_traces.py --verify   # publish, then confirm
"""

import argparse
import base64
import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.config import settings  # noqa: E402

PAGE = 100
# Ingestion accepts a batch; 50 keeps each request small enough to stay well inside any
# body-size limit while still making this a handful of calls rather than a hundred.
BATCH = 50


def _auth_header() -> dict:
    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        sys.exit("Langfuse keys are not set in utils/.env -- nothing to do.")
    token = base64.b64encode(
        f"{settings.langfuse_public_key}:{settings.langfuse_secret_key}".encode()
    ).decode()
    return {"Authorization": f"Basic {token}", "Content-Type": "application/json"}


def _host() -> str:
    return settings.langfuse_host.rstrip("/")


def _get(path: str, headers: dict) -> dict:
    req = urllib.request.Request(_host() + path, headers=headers)
    return json.load(urllib.request.urlopen(req, timeout=60))


def list_traces(headers: dict) -> list:
    """Every trace in the project, paged. Returns [(id, name, public)]."""
    out, page = [], 1
    while True:
        data = _get(f"/api/public/traces?limit={PAGE}&page={page}", headers)
        items = data.get("data") or []
        out += [(t["id"], t.get("name") or "", bool(t.get("public"))) for t in items]
        total = (data.get("meta") or {}).get("totalItems")
        if not items or (total is not None and len(out) >= total):
            break
        page += 1
    return out


def publish(trace_ids: list, headers: dict) -> tuple:
    """Upserts `public: true` on each id. Returns (accepted, errors)."""
    accepted, errors = 0, []
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    for i in range(0, len(trace_ids), BATCH):
        chunk = trace_ids[i:i + BATCH]
        body = {
            "batch": [
                {
                    "id": str(uuid.uuid4()),
                    "type": "trace-create",
                    "timestamp": now,
                    # ONLY id and public. Every other field is omitted so the upsert cannot
                    # overwrite a name, input or output that is already there.
                    "body": {"id": tid, "public": True},
                }
                for tid in chunk
            ]
        }
        req = urllib.request.Request(
            _host() + "/api/public/ingestion",
            data=json.dumps(body).encode(),
            headers=headers,
            method="POST",
        )
        try:
            res = json.load(urllib.request.urlopen(req, timeout=90))
            accepted += len(res.get("successes") or [])
            errors += res.get("errors") or []
        except urllib.error.HTTPError as e:
            errors.append({"http": e.code, "detail": e.read()[:200].decode(errors="replace")})
        print(f"  batch {i // BATCH + 1}: {len(chunk)} sent")
    return accepted, errors


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="report what would change, write nothing")
    ap.add_argument("--verify", action="store_true", help="poll afterwards until every trace reads public")
    args = ap.parse_args()

    headers = _auth_header()
    traces = list_traces(headers)
    private = [t for t in traces if not t[2]]
    print(f"project: {_host()}")
    print(f"traces: {len(traces)} total · {len(traces) - len(private)} public · {len(private)} private")

    if not private:
        print("Every trace is already public. Nothing to do.")
        return 0
    if args.dry_run:
        print(f"[dry run] would publish {len(private)} trace(s); nothing was written.")
        return 0

    accepted, errors = publish([t[0] for t in private], headers)
    print(f"accepted: {accepted} · errors: {len(errors)}")
    for e in errors[:5]:
        print("  ERROR", json.dumps(e)[:200])

    if not args.verify:
        print("Ingestion is async; allow ~20s before the flag shows. Re-run with --verify to confirm.")
        return 1 if errors else 0

    # Poll rather than sleep once: propagation was ~16s when measured, but it is a queue and
    # a queue's latency is not a constant worth hardcoding.
    for attempt in range(12):
        time.sleep(10)
        still = [t for t in list_traces(headers) if not t[2]]
        print(f"  +{(attempt + 1) * 10}s · {len(still)} still private")
        if not still:
            print("VERIFIED: every trace in the project is public.")
            return 0
    print(f"WARNING: {len(still)} trace(s) still private after 120s.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
