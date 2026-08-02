"""Create an immutable Context Store version from businesslogic.md.

Run this only for migration/bootstrap. Normal writes belong to the Context Agent's
Context Store MCP operation, which must use the same append-only protocol.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

import clickhouse_connect


EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536


def split_sections(markdown: str) -> list[tuple[str, str]]:
    sections = re.split(r"(?=^## )", markdown, flags=re.MULTILINE)
    return [
        (match.group(1).strip() if (match := re.match(r"##\s+(.+)", section)) else "metadata", section.strip())
        for section in sections
        if section.strip()
    ]


def embeddings(texts: list[str]) -> list[list[float]]:
    api_key = os.environ["OPENAI_API_KEY"]
    request = Request(
        "https://api.openai.com/v1/embeddings",
        headers={"Authorization": f"Bearer {api_key}"},
        data=json.dumps({"model": EMBEDDING_MODEL, "input": texts, "encoding_format": "float"}).encode(),
        method="POST",
    )
    request.add_header("Content-Type", "application/json")
    with urlopen(request, timeout=60) as response:
        vectors = [item["embedding"] for item in json.load(response)["data"]]
    if len(vectors) != len(texts) or any(len(vector) != EMBEDDING_DIMENSIONS for vector in vectors):
        raise RuntimeError("Embedding response did not match the configured 1536-dimension contract")
    return vectors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=8443)
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--secure", action="store_true")
    args = parser.parse_args()

    markdown = args.file.read_text()
    digest = hashlib.sha256(markdown.encode()).hexdigest()
    client = clickhouse_connect.get_client(
        host=args.host, port=args.port, username=args.username, password=args.password, secure=args.secure, database="agent"
    )
    existing = client.query(
        "SELECT version_number FROM business_logic_versions WHERE content_sha256 = {digest:String} "
        "AND status = 'published' ORDER BY version_number DESC LIMIT 1",
        parameters={"digest": digest},
    ).result_rows
    if existing:
        print(f"context store already contains version {existing[0][0]} for this content")
        return

    prior = client.query(
        "SELECT context_id, version_number FROM business_logic_versions WHERE status = 'published' "
        "ORDER BY version_number DESC LIMIT 1"
    ).result_rows
    context_id = str(uuid.uuid4())
    version_number = int(prior[0][1]) + 1 if prior else 1
    previous_context_id = str(prior[0][0]) if prior else None
    timestamp = datetime.now(timezone.utc)
    chunks = split_sections(markdown)
    vectors = embeddings([text for _, text in chunks])

    chunk_rows = []
    for ordinal, ((section_type, text), vector) in enumerate(zip(chunks, vectors)):
        chunk_rows.append({
            "context_id": context_id,
            "version_number": version_number,
            "chunk_id": str(uuid.uuid4()),
            "chunk_ordinal": ordinal,
            "section_type": section_type.lower().replace(" ", "_"),
            "entity_type": "context_section",
            "entity_id": section_type,
            "valid_from": timestamp,
            "valid_to": None,
            "status": "published",
            "confidence": 1.0,
            "content_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "chunk_text": text,
            "metadata_json": json.dumps({"embedding_model": EMBEDDING_MODEL, "source": str(args.file)}),
            "embedding": vector,
        })
    client.insert("business_logic_embeddings_v1", [list(row.values()) for row in chunk_rows], column_names=list(chunk_rows[0]))
    client.insert("business_logic_versions", [[
        context_id, version_number, previous_context_id, "published", timestamp, timestamp, digest,
        markdown, json.dumps({"context_version": f"context-{version_number}", "source": str(args.file)}),
        "Initial migration from businesslogic.md", None, [], EMBEDDING_MODEL, EMBEDDING_DIMENSIONS, "context-agent-migration",
    ]], column_names=[
        "context_id", "version_number", "previous_context_id", "status", "effective_at", "published_at", "content_sha256",
        "snapshot_markdown", "snapshot_json", "change_summary", "source_run_id", "source_query_ids", "embedding_model",
        "embedding_dimensions", "created_by",
    ])
    stored = client.query(
        "SELECT count() FROM business_logic_embeddings_v1 WHERE context_id = {context_id:UUID}",
        parameters={"context_id": context_id},
    ).result_rows[0][0]
    if stored != len(chunk_rows):
        raise RuntimeError(f"Expected {len(chunk_rows)} chunks, stored {stored}")
    print(f"seeded context store version {version_number} with {stored} embedded sections")


if __name__ == "__main__":
    main()
