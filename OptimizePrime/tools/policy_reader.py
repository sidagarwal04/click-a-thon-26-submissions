"""policy_reader — read policy/model.policy from Python, with no ClickHouse.

Summary: policy/model.policy is the single declaration of every tuned constant
(ADR 0032). SQL reads it through the generated view ``v_model_policy``; shell
reads it through ``tools/policy.sh``; this module is the third reader, so the
offline oracle and the fixture generators bind to the same values instead of
carrying their own copies. Deliberately dependency-free and DB-free: the
reference interpreter must stay runnable on a JSON file with nothing else up.
"""

from __future__ import annotations

import hashlib
import os
from typing import Dict

__all__ = ["load", "get", "get_int", "version", "content_hash", "stamp", "POLICY_PATH"]

POLICY_PATH = os.environ.get(
    "MODEL_POLICY_FILE",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir,
                 "policy", "model.policy"),
)

_CACHE: Dict[str, str] = {}


def load(path: str | None = None) -> Dict[str, str]:
    """Parse the declaration into {KEY: value-as-string}.

    The format is plain ``KEY=VALUE`` precisely so that three languages can
    read it without a shared parser. ``#:`` annotation lines carry the SQL type
    and note for the generator and are ignored here.
    """
    global _CACHE
    if path is None and _CACHE:
        return dict(_CACHE)
    p = path or POLICY_PATH
    out: Dict[str, str] = {}
    with open(p, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                raise ValueError(f"{p}: unparseable line: {line!r}")
            key, val = line.split("=", 1)
            val = val.split("#", 1)[0].strip()
            out[key.strip()] = val
    if not out:
        raise ValueError(f"{p}: declared nothing — refusing to run with no policy")
    if path is None:
        _CACHE = dict(out)
    return out


def get(key: str, path: str | None = None) -> str:
    vals = load(path)
    try:
        return vals[key]
    except KeyError:
        raise KeyError(
            f"policy key {key!r} is not declared in {path or POLICY_PATH} — "
            f"declared keys: {', '.join(sorted(vals))}"
        ) from None


def get_int(key: str, path: str | None = None) -> int:
    return int(get(key, path))


def version(path: str | None = None) -> str:
    return get("POLICY_VERSION", path)


def content_hash(path: str | None = None) -> str:
    """Same canonical form as tools/policy.sh: sorted KEY=VALUE, sha256, 12 hex."""
    vals = load(path)
    canon = "".join(f"{k}={vals[k]}\n" for k in sorted(vals))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()[:12]


def stamp(path: str | None = None) -> str:
    v = load(path)
    keys = ("GAP_S", "TAIL_S", "UNCLOSED_PAUSE_TO_RUN_END", "POINT_ACTIVITY_COUNTS")
    body = " ".join(f"{k}={v[k]}" for k in keys if k in v)
    return f"policy v{version(path)} ({content_hash(path)}) {body}"


if __name__ == "__main__":  # `python3 tools/policy_reader.py` prints the stamp
    print(stamp())
