"""Central config + env access. No magic strings elsewhere — read from here."""
import json
import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

_CONFIG_PATH = Path(__file__).resolve().parent / "config.json"


@lru_cache
def config() -> dict:
    return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))


def env(key: str, default: str | None = None) -> str | None:
    return os.environ.get(key, default)


# ---- dataset selection -----------------------------------------------------
#
# Two table sets live side by side: `dev` (Jun 1 - Jul 5, the tables we built against) and
# `unseen` (the sealed Jul 6-10 slice, streamed in). Every accessor below resolves the name at
# CALL time — module-level constants captured at import would silently ignore a switch.
#
# TARGET is the window under investigation; HISTORY is where baselines and model training read
# from. They are separate on purpose: the unseen slice is only 5 days, far short of the
# same-weekday trailing-3-weeks baseline, so history keeps coming from `dev`.

_TARGET_ENV = "RCA_DATASET"          # override the target dataset without editing config.json
_HISTORY_ENV = "RCA_HISTORY_DATASET"


def dataset_name(role: str = "target") -> str:
    """Active dataset key for 'target' or 'history'."""
    if role == "history":
        return env(_HISTORY_ENV) or config()["history_dataset"]
    return env(_TARGET_ENV) or config()["active_dataset"]


def tables(role: str = "target") -> dict:
    """Table-name map ({events, enriched, hourly, apps, advertisers, geo_device}) for a role."""
    name = dataset_name(role)
    try:
        return config()["datasets"][name]
    except KeyError:
        raise ValueError(f"unknown dataset {name!r}; expected one of {list(config()['datasets'])}") from None


def target_hourly() -> str:
    """Hourly rollup holding the window being investigated."""
    return tables("target")["hourly"]


def baseline_hourly() -> str:
    """Hourly rollup holding history — baselines and model training always read here."""
    return tables("history")["hourly"]


def hourly_source() -> str:
    """FROM-clause source covering the target window AND its baseline in one scan.

    Most queries here read both at once (`WHERE (target_window OR baseline_window)`), which a
    single table name cannot express once the two live in different datasets. The datasets cover
    DISJOINT date ranges — dev is Jun 1-Jul 5, unseen is Jul 6-10 — so UNION ALL is safe: no
    hour is counted twice, and the existing time filters select the right side on their own.

    Collapses to a plain table name whenever target and history are the same dataset, so the
    default dev path emits exactly the SQL it always did.
    """
    target, history = target_hourly(), baseline_hourly()
    if target == history:
        return target
    return f"(SELECT * FROM {target} UNION ALL SELECT * FROM {history})"


CLICKHOUSE = {
    "host": env("CLICKHOUSE_HOST"),
    "port": int(env("CLICKHOUSE_PORT", "8443")),
    "username": env("CLICKHOUSE_USER", "default"),
    "password": env("CLICKHOUSE_PASSWORD"),
    "database": env("CLICKHOUSE_DATABASE", "default"),
}

LANGFUSE = {
    "public_key": env("LANGFUSE_PUBLIC_KEY"),
    "secret_key": env("LANGFUSE_SECRET_KEY"),
    # SDK ingestion host. In Docker this is the internal service (langfuse-web:3000).
    "host": env("LANGFUSE_HOST", "http://localhost:3000"),
    # Browser-facing base for trace LINKS. The SDK bakes `host` into get_trace_url(), but a
    # container-internal host (langfuse-web:3000) can't be opened from the host browser — so
    # trace URLs are rewritten to this. Defaults to `host` (correct for a host venv run).
    "public_host": env("LANGFUSE_PUBLIC_HOST") or env("LANGFUSE_HOST", "http://localhost:3000"),
    # Publish every investigation trace so its URL opens without a Langfuse login. The trace
    # link is a scored deliverable ("no trace, no credit"), and a judge who has to sign up
    # lands in their own empty org and sees "You do not have access to this trace" - which is
    # exactly what happened. Off by default: publishing is irreversible and only appropriate
    # for a demo dataset with no real customer data in it.
    "publish_traces": env("LANGFUSE_PUBLISH_TRACES", "false").lower() in ("1", "true", "yes"),
}

# AWS Bedrock — auth comes from the standard AWS credential chain (aws cli / env / role),
# so no key is stored here. Region + model default to config.json; env can override.
BEDROCK = {
    "region": env("AWS_REGION") or config()["bedrock"]["region"],
    "model_id": env("BEDROCK_MODEL_ID") or config()["bedrock"]["model_id"],
}
