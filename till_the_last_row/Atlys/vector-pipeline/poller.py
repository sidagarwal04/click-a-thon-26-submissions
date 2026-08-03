#!/usr/bin/env python3
"""
Vector exec-source poller: atlys.otel_logs → NDJSON stdout.

Reads rows from ClickHouse in batches, tracks progress via a checkpoint file,
and writes one flat JSON object per line to stdout.  Vector's exec source
reads this output and feeds it into the transform/sink pipeline.
"""

import json
import os
import sys
import time
import logging
from datetime import datetime

import clickhouse_connect

# ---------------------------------------------------------------------------
# Configuration — overridable via environment variables
# ---------------------------------------------------------------------------
CH_HOST      = os.environ.get("CH_HOST",      "lyab2g0slj.eastus2.azure.clickhouse.cloud")
CH_PORT      = int(os.environ.get("CH_PORT",  "8443"))
CH_USER      = os.environ.get("CH_USER",      "default")
CH_PASSWORD  = os.environ.get("CH_PASSWORD",  "IAe_cPA4PukDz")
CH_DATABASE  = os.environ.get("CH_DATABASE",  "atlys")

CHECKPOINT_FILE = os.environ.get("CHECKPOINT_FILE", "/data/checkpoint.txt")
BATCH_SIZE      = int(os.environ.get("BATCH_SIZE",    "10000"))
POLL_INTERVAL_S = int(os.environ.get("POLL_INTERVAL_S", "30"))

SOURCE_TABLE = "otel_logs"

# ---------------------------------------------------------------------------
# Logging — stderr only so it never pollutes the NDJSON stdout stream
# ---------------------------------------------------------------------------
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s [poller] %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Checkpoint helpers
# ---------------------------------------------------------------------------

def read_checkpoint() -> str:
    """Return last processed Timestamp string, or epoch start."""
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE) as fh:
            value = fh.read().strip()
            if value:
                return value
    return "1970-01-01 00:00:00"


def write_checkpoint(ts: str) -> None:
    os.makedirs(os.path.dirname(CHECKPOINT_FILE), exist_ok=True)
    tmp = CHECKPOINT_FILE + ".tmp"
    with open(tmp, "w") as fh:
        fh.write(ts)
    os.replace(tmp, CHECKPOINT_FILE)


# ---------------------------------------------------------------------------
# ClickHouse client factory
# ---------------------------------------------------------------------------

def make_client():
    return clickhouse_connect.get_client(
        host=CH_HOST,
        port=CH_PORT,
        username=CH_USER,
        password=CH_PASSWORD,
        database=CH_DATABASE,
        secure=True,
        verify=False,
    )


# ---------------------------------------------------------------------------
# Row extraction
# ---------------------------------------------------------------------------

def _s(d: dict, key: str) -> str:
    """Extract a string field; return '' for None / missing."""
    v = d.get(key)
    return str(v) if v is not None else ""


def row_to_flat(raw: dict) -> dict | None:
    """
    Flatten a raw otel_logs row into a single dict ready for Vector VRL.
    Returns None if the row has no atlys.table tag (skip it).
    """
    try:
        resource_attrs: dict = raw.get("ResourceAttributes") or {}
        log_attrs: dict      = raw.get("LogAttributes")      or {}

        atlys_table = resource_attrs.get("atlys.table", "").strip()
        if not atlys_table:
            return None

        flat: dict = {"atlys_table": atlys_table}

        # ── Common envelope ────────────────────────────────────────────────
        flat["id"]                       = _s(log_attrs, "id")
        flat["timestamp"]                = _s(log_attrs, "timestamp")
        flat["user_id"]                  = _s(log_attrs, "user_id")
        flat["application_id"]           = _s(log_attrs, "application_id")
        flat["app_session_id"]           = _s(log_attrs, "app_session_id")
        flat["device"]                   = _s(log_attrs, "device")
        flat["device_type"]              = _s(log_attrs, "device_type")
        flat["os"]                       = _s(log_attrs, "os")
        flat["app_version"]              = _s(log_attrs, "app_version")
        flat["client_lib"]               = _s(log_attrs, "client_lib")
        flat["geoip_country_code"]       = _s(log_attrs, "geoip_country_code")
        flat["geoip_subdivision_1_code"] = _s(log_attrs, "geoip_subdivision_1_code")
        flat["city"]                     = _s(log_attrs, "city")
        flat["client_ip"]                = _s(log_attrs, "client_ip")
        flat["latitude"]                 = _s(log_attrs, "latitude")
        flat["longitude"]                = _s(log_attrs, "longitude")
        flat["locale"]                   = _s(log_attrs, "locale")
        flat["language"]                 = _s(log_attrs, "language")
        flat["funnel_type"]              = _s(log_attrs, "funnel_type")
        flat["co_travelers"]             = _s(log_attrs, "co_travelers")
        flat["is_guest"]                 = _s(log_attrs, "is_guest")
        flat["is_referral"]              = _s(log_attrs, "is_referral")
        flat["is_enterprise"]            = _s(log_attrs, "is_enterprise")
        flat["gclid"]                    = _s(log_attrs, "gclid")
        flat["fbclid"]                   = _s(log_attrs, "fbclid")
        flat["gad_source"]               = _s(log_attrs, "gad_source")
        flat["citizenship"]              = _s(log_attrs, "citizenship")
        flat["destination"]              = _s(log_attrs, "destination")
        flat["is_back_filled"]           = _s(log_attrs, "is_back_filled")
        flat["duplicate_id"]             = _s(log_attrs, "duplicate_id")

        # ── Event-specific fields (all extracted; VRL selects per table) ──
        flat["visa_type"]                = _s(log_attrs, "visa_type")
        flat["card_type"]                = _s(log_attrs, "card_type")
        flat["page_version"]             = _s(log_attrs, "page_version")
        flat["flow"]                     = _s(log_attrs, "flow")
        flat["is_guest_browse"]          = _s(log_attrs, "is_guest_browse")

        flat["purpose"]                  = _s(log_attrs, "purpose")
        flat["eta_shown"]                = _s(log_attrs, "eta_shown")

        flat["auth_method"]              = _s(log_attrs, "auth_method")
        flat["is_new_user"]              = _s(log_attrs, "is_new_user")
        flat["attempts"]                 = _s(log_attrs, "attempts")

        flat["doc_type"]                 = _s(log_attrs, "doc_type")
        flat["capture_mode"]             = _s(log_attrs, "capture_mode")
        flat["scan_mode"]                = _s(log_attrs, "scan_mode")
        flat["retry_count"]              = _s(log_attrs, "retry_count")
        flat["failed_attempt_threshold"] = _s(log_attrs, "failed_attempt_threshold")
        flat["is_crossed_failed_attempt_threshold"] = _s(
            log_attrs, "is_crossed_failed_attempt_threshold"
        )

        flat["payment_method"]           = _s(log_attrs, "payment_method")
        flat["amount"]                   = _s(log_attrs, "amount")
        flat["currency"]                 = _s(log_attrs, "currency")
        flat["coupon_applied"]           = _s(log_attrs, "coupon_applied")
        flat["plan_selected"]            = _s(log_attrs, "plan_selected")

        flat["value"]                    = _s(log_attrs, "value")
        flat["coupon_name"]              = _s(log_attrs, "coupon_name")
        flat["discount_amount"]          = _s(log_attrs, "discount_amount")
        flat["insurance_added"]          = _s(log_attrs, "insurance_added")
        flat["insurance_amount"]         = _s(log_attrs, "insurance_amount")

        flat["scroll_depth_pct"]         = _s(log_attrs, "scroll_depth_pct")
        flat["time_on_page_s"]           = _s(log_attrs, "time_on_page_s")

        flat["search_term"]              = _s(log_attrs, "search_term")
        flat["results_count"]            = _s(log_attrs, "results_count")
        flat["source"]                   = _s(log_attrs, "source")

        return flat

    except Exception as exc:
        log.warning("Failed to parse row: %s | keys: %s", exc, list(raw.keys()))
        return None


# ---------------------------------------------------------------------------
# Poll one batch
# ---------------------------------------------------------------------------

def poll_once(client, checkpoint: str) -> str:
    query = f"""
        SELECT
            Body,
            ResourceAttributes,
            LogAttributes,
            Timestamp
        FROM {CH_DATABASE}.{SOURCE_TABLE}
        WHERE Timestamp > '{checkpoint}'
        ORDER BY Timestamp ASC
        LIMIT {BATCH_SIZE}
    """

    log.info("Fetching after checkpoint=%s (limit=%d)", checkpoint, BATCH_SIZE)
    result = client.query(query)
    rows   = result.named_results()

    if not rows:
        log.info("No new rows.")
        return checkpoint

    new_checkpoint = checkpoint
    emitted = 0

    for raw in rows:
        flat = row_to_flat(raw)
        if flat is None:
            continue

        ts_val = raw.get("Timestamp")
        if ts_val:
            ts_str = (
                ts_val.strftime("%Y-%m-%d %H:%M:%S")
                if isinstance(ts_val, datetime)
                else str(ts_val)
            )
            if ts_str > new_checkpoint:
                new_checkpoint = ts_str

        print(json.dumps(flat, default=str), flush=True)
        emitted += 1

    log.info(
        "Emitted %d/%d rows; new checkpoint=%s", emitted, len(rows), new_checkpoint
    )
    return new_checkpoint


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    log.info(
        "Poller starting — checkpoint_file=%s batch=%d poll_interval=%ds",
        CHECKPOINT_FILE, BATCH_SIZE, POLL_INTERVAL_S,
    )
    client     = make_client()
    checkpoint = read_checkpoint()

    while True:
        try:
            new_cp = poll_once(client, checkpoint)
            if new_cp != checkpoint:
                write_checkpoint(new_cp)
                checkpoint = new_cp
        except Exception as exc:
            log.error("Poll error: %s — retrying after %ds", exc, POLL_INTERVAL_S)

        log.info("Sleeping %ds …", POLL_INTERVAL_S)
        time.sleep(POLL_INTERVAL_S)


if __name__ == "__main__":
    main()
