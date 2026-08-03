#!/usr/bin/env python3
"""Static contract test for the ClickStack filter and source-provisioning surface.

The test is deliberately offline: it never reads .env, calls ClickStack, or mutates ClickHouse.
It keeps the session-minute view, both source select expressions, and the hosted dashboard's named
filters aligned with every dimension the official delivered and unseen datasets declare filterable.
It also prevents the former false-idempotence bug where an existing named source was skipped and
silently retained an obsolete select expression. Run: python3 tools/clickstack-static-test.py.
"""

from pathlib import Path


FILTER_DIMENSIONS = (
    "content_id",
    "title",
    "video_type",
    "category",
    "show_name",
    "platform",
    "country",
    "app_version",
    "audio_language",
    "subtitle_language",
    "player_version",
    "video_resolution",
)


def require_dimensions(label: str, text: str, token_template: str = "{}") -> None:
    missing = [
        dimension
        for dimension in FILTER_DIMENSIONS
        if token_template.format(dimension) not in text
    ]
    if missing:
        raise SystemExit(f"{label} missing dimensions: {', '.join(missing)}")


root = Path(__file__).resolve().parent.parent
sql = (root / "sql/87_viz.sql").read_text()
cloud = (root / "tools/clickstack-cloud.sh").read_text()
self_hosted = (root / "tools/clickstack-sources.sh").read_text()

session_view = sql.split("CREATE OR REPLACE VIEW v_session_minutes AS", 1)[1].split(
    "CREATE OR REPLACE VIEW v_cc_by_video_resolution AS", 1
)[0]
require_dimensions("v_session_minutes", session_view, " AS {}")

filter_block = cloud.split(
    '"name": "SonyLIV drilldown — sessions & users"', 1
)[1].split('"tiles": [', 1)[0]
require_dimensions("hosted dashboard filters", filter_block, '"{}"')

cloud_select = next(
    line
    for line in cloud.splitlines()
    if line.strip().startswith('"minute, video_session_id')
)
self_hosted_select = next(
    line
    for line in self_hosted.splitlines()
    if 'add_source "Session minutes (filters)"' in line
)
require_dimensions("hosted drilldown source", cloud_select)
require_dimensions("self-hosted drilldown source", self_hosted_select)

for label, script in (("hosted", cloud), ("self-hosted", self_hosted)):
    if 'payload["id"] = os.environ["SOURCE_ID"]' not in script:
        raise SystemExit(f"{label} source update omits the required source id")
    if "/sources/$existing" not in script or "-X PUT" not in script:
        raise SystemExit(f"{label} source update does not use PUT /sources/:id")
    if "source '$name' exists" in script:
        raise SystemExit(f"{label} provisioner still skips existing sources")

schema_apply = (
    "TARGET=cloud tools/apply-sql.sh sql/00_schema.sql "
    "sql/10_intervals.sql sql/87_viz.sql"
)
if schema_apply not in cloud:
    raise SystemExit("hosted provisioner does not converge filter-view schema dependencies")

print(
    "ClickStack static contract: PASS "
    f"({len(FILTER_DIMENSIONS)}/{len(FILTER_DIMENSIONS)} dimensions; "
    "hosted and self-hosted source PUT convergence)"
)
