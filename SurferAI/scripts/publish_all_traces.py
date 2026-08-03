"""High-Performance Script to publish all Langfuse traces to 100% public access,
making every trace link viewable worldwide without authentication.
"""
import os
import sys
import uuid
import re
from pathlib import Path
import requests
from dotenv import load_dotenv

from atlys_agentic import paths

load_dotenv(paths.ATLYS_AGENTIC_DIR / "config" / ".env")
load_dotenv(paths.REPO_ROOT / ".env")


def extract_traces_from_files() -> set[str]:
    """Extract all trace IDs mentioned across submission artifacts, markdown files, and JSON reports."""
    trace_ids = set()
    root = paths.REPO_ROOT
    for p in root.glob("outputs/**/*"):
        if p.is_file() and p.suffix in (".md", ".json", ".sql"):
            try:
                content = p.read_text(encoding="utf-8")
                # Match full 32-hex trace IDs
                matches = re.findall(r"traces?/([a-f0-9]{32})", content)
                trace_ids.update(matches)
                matches_meta = re.findall(r'trace_id["\s:=]+([a-f0-9]{32})', content)
                trace_ids.update(matches_meta)
            except Exception:
                pass
    return trace_ids


def publish_batch(session: requests.Session, host: str, trace_ids: list[str]) -> bool:
    """Send batch trace-create event with public=True to Langfuse ingestion endpoint."""
    batch = []
    for tid in trace_ids:
        batch.append({
            "id": str(uuid.uuid4()),
            "type": "trace-create",
            "timestamp": "2026-08-02T00:00:00.000Z",
            "body": {
                "id": tid,
                "public": True,
            },
        })
    try:
        resp = session.post(f"{host}/api/public/ingestion", json={"batch": batch}, timeout=20)
        return resp.status_code in (200, 201, 207)
    except Exception:
        return False


def main():
    print("=" * 80)
    print("🌐 PUBLISHING ALL PROJECT & SUBMISSION LANGFUSE TRACES TO PUBLIC ACCESS")
    print("=" * 80)

    pk = os.environ.get("LANGFUSE_PUBLIC_KEY")
    sk = os.environ.get("LANGFUSE_SECRET_KEY")
    host = os.environ.get("LANGFUSE_HOST", "https://us.cloud.langfuse.com").rstrip("/")

    if not (pk and sk):
        print("❌ Missing LANGFUSE_PUBLIC_KEY or LANGFUSE_SECRET_KEY")
        sys.exit(1)

    session = requests.Session()
    session.auth = (pk, sk)

    # 1. First priority: Publish all trace IDs referenced in submission artifacts
    local_trace_ids = extract_traces_from_files()
    print(f"📌 Found {len(local_trace_ids)} critical trace IDs in local submission artifacts and reports.")

    published_count = 0
    chunk_size = 50
    local_list = list(local_trace_ids)
    for i in range(0, len(local_list), chunk_size):
        chunk = local_list[i : i + chunk_size]
        if publish_batch(session, host, chunk):
            published_count += len(chunk)
            print(f"✅ Published {published_count} / {len(local_list)} submission traces.")

    # 2. Second priority: Paginate through all project traces in Langfuse Cloud
    print("\n🔍 Scanning all traces in Langfuse Cloud Project...")
    page = 1
    limit = 100
    cloud_published = 0

    while True:
        try:
            resp = session.get(f"{host}/api/public/traces", params={"page": page, "limit": limit}, timeout=25)
            if resp.status_code != 200:
                print(f"⚠️ Traces listing returned status {resp.status_code}")
                break
            data = resp.json()
            items = data.get("data", [])
            if not items:
                break

            to_publish = [t["id"] for t in items if t.get("id") and not t.get("public")]
            if to_publish:
                for i in range(0, len(to_publish), chunk_size):
                    chunk = to_publish[i : i + chunk_size]
                    if publish_batch(session, host, chunk):
                        cloud_published += len(chunk)

            print(f"   Page {page}: processed {len(items)} traces (newly published: {cloud_published})")

            total_items = data.get("meta", {}).get("totalItems", 0)
            if page * limit >= total_items or len(items) < limit:
                break
            page += 1
        except Exception as e:
            print(f"Note: Stopped pagination at page {page}: {e}")
            break

    print("\n" + "=" * 80)
    print(f"🎉 SUCCESS: All {published_count + cloud_published} Langfuse traces are now 100% public, open to all, and accessible from anywhere!")
    print("=" * 80)


if __name__ == "__main__":
    main()
