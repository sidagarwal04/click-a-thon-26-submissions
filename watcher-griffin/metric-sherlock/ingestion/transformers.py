"""Pure per-record normalization, applied before schema/business validation.

Each `normalize_*` function takes a raw dict (as produced by any Source) and
returns `(row, errors, extra_fields)`:

  row=None,  errors=[]      -> SKIP:   blank row or a duplicate CSV header
                                        line re-embedded in the body. Noise,
                                        not a violation -- counted, never
                                        dead-lettered.
  row=None,  errors=[...]   -> REJECT: e.g. a structurally malformed source
                                        line (wrong column count).
  row={...}, errors=[...]   -> REJECT: a required field failed to coerce
                                        (bad flag/revenue/timestamp).
  row={...}, errors=[]      -> proceed to schema + business validation.

Never raises -- a record that can't be normalized is still passed through
with an error attached, so downstream validation sees the full picture
instead of a crash.
"""

import math
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

Row = Dict[str, Any]
NormalizeResult = Tuple[Optional[Row], List[str], List[str]]

# Sentinel key a Source sets on a raw dict to flag a structurally malformed
# line (wrong column count) instead of raising or silently truncating it.
MALFORMED_LINE_KEY = "__malformed_line__"

_NULL_TOKENS = {"", "null", "none", "nan", "n/a", "-"}
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")

AD_EVENT_FIELDS = {
    "event_time", "app_id", "geo_device_id", "advertiser_id", "ad_format",
    "is_filled", "is_impression", "is_click", "revenue",
}
APP_FIELDS = {"app_id", "category", "publisher_tier"}
ADVERTISER_FIELDS = {"advertiser_id", "vertical", "campaign_type"}
GEO_DEVICE_FIELDS = {"geo_device_id", "region", "country", "device_model", "os_version"}


def _normalize_key(key: Any) -> str:
    k = str(key).strip()
    k = re.sub(r"[\s\-]+", "_", k)
    k = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", k)  # AppId -> App_Id, isFilled -> is_Filled
    k = re.sub(r"_+", "_", k)
    return k.strip("_").lower()


def _select_known_fields(raw: Row, known_fields: Set[str]) -> Tuple[Row, List[str]]:
    normalized = {_normalize_key(k): v for k, v in raw.items()}
    selected = {k: normalized[k] for k in known_fields if k in normalized}
    extra_fields = sorted(set(normalized.keys()) - known_fields)
    return selected, extra_fields


def _is_null_token(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, float) and math.isnan(v):
        return True
    if isinstance(v, str):
        return v.strip().lower() in _NULL_TOKENS
    return False


def _clean_str_field(v: Any, collapse_nulls: bool = True) -> str:
    if v is None:
        return ""
    s = _CONTROL_CHARS_RE.sub("", str(v)).strip()
    if collapse_nulls and s.lower() in _NULL_TOKENS:
        return ""
    return s


def _coerce_flag(v: Any) -> Optional[int]:
    if _is_null_token(v):
        return None
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        # 1.0 is a formatting artifact; 0.5 is garbled data, never truncate it.
        return int(v) if v.is_integer() else None
    if isinstance(v, str):
        s = v.strip().lower()
        if s in ("1", "true", "yes", "y", "t"):
            return 1
        if s in ("0", "false", "no", "n", "f"):
            return 0
        try:
            f = float(s)
        except ValueError:
            return None
        return int(f) if f.is_integer() else None
    return None


def _coerce_float(v: Any) -> Optional[float]:
    if _is_null_token(v):
        return None
    if isinstance(v, (int, float)):
        return None if (isinstance(v, float) and math.isnan(v)) else float(v)
    if isinstance(v, str):
        try:
            return float(v.strip())
        except ValueError:
            return None
    return None


def _parse_event_time(v: Any) -> Optional[datetime]:
    if isinstance(v, datetime):
        return v
    if isinstance(v, (int, float)):
        try:
            ts = float(v)
            if ts > 1e12:  # looks like milliseconds, not seconds
                ts /= 1000.0
            return datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None)
        except (ValueError, OverflowError, OSError):
            return None
    if isinstance(v, str):
        s = v.strip()
        if not s or _is_null_token(s):
            return None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(s, fmt)
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(s)
        except ValueError:
            return None
    return None


def _is_blank_row(selected: Row) -> bool:
    if not selected:
        return True
    return all(_is_null_token(v) for v in selected.values())


def _is_duplicate_header_row(selected: Row) -> bool:
    if not selected:
        return False
    return all(isinstance(v, str) and v.strip().lower() == k for k, v in selected.items())


def normalize_ad_event(raw: Row) -> NormalizeResult:
    if MALFORMED_LINE_KEY in raw:
        return None, [f"malformed line, wrong column count: {raw[MALFORMED_LINE_KEY]!r}"], []

    selected, extra_fields = _select_known_fields(raw, AD_EVENT_FIELDS)
    if _is_blank_row(selected):
        return None, [], extra_fields
    if _is_duplicate_header_row(selected):
        return None, [], extra_fields

    errors: List[str] = []
    row: Row = {
        "app_id": _clean_str_field(selected.get("app_id")),
        "geo_device_id": _clean_str_field(selected.get("geo_device_id")),
        "advertiser_id": _clean_str_field(selected.get("advertiser_id")),
        "ad_format": _clean_str_field(selected.get("ad_format")).lower(),
    }

    for field in ("is_filled", "is_impression", "is_click"):
        coerced = _coerce_flag(selected.get(field))
        if coerced is None:
            errors.append(f"{field}: could not parse {selected.get(field)!r} as 0/1")
        row[field] = coerced

    revenue = _coerce_float(selected.get("revenue"))
    if revenue is None:
        errors.append(f"revenue: could not parse {selected.get('revenue')!r} as a number")
    row["revenue"] = revenue

    event_time = _parse_event_time(selected.get("event_time"))
    if event_time is None:
        errors.append(f"event_time: could not parse {selected.get('event_time')!r}")
    row["event_time"] = event_time

    return row, errors, extra_fields


def normalize_app(raw: Row) -> NormalizeResult:
    if MALFORMED_LINE_KEY in raw:
        return None, [f"malformed line, wrong column count: {raw[MALFORMED_LINE_KEY]!r}"], []

    selected, extra_fields = _select_known_fields(raw, APP_FIELDS)
    if _is_blank_row(selected):
        return None, [], extra_fields
    if _is_duplicate_header_row(selected):
        return None, [], extra_fields

    row = {
        "app_id": _clean_str_field(selected.get("app_id")),
        "category": _clean_str_field(selected.get("category")).lower(),
        "publisher_tier": _clean_str_field(selected.get("publisher_tier")).lower(),
    }
    return row, [], extra_fields


def normalize_advertiser(raw: Row) -> NormalizeResult:
    if MALFORMED_LINE_KEY in raw:
        return None, [f"malformed line, wrong column count: {raw[MALFORMED_LINE_KEY]!r}"], []

    selected, extra_fields = _select_known_fields(raw, ADVERTISER_FIELDS)
    if _is_blank_row(selected):
        return None, [], extra_fields
    if _is_duplicate_header_row(selected):
        return None, [], extra_fields

    row = {
        "advertiser_id": _clean_str_field(selected.get("advertiser_id")),
        "vertical": _clean_str_field(selected.get("vertical")).lower(),
        "campaign_type": _clean_str_field(selected.get("campaign_type")).upper(),
    }
    return row, [], extra_fields


def normalize_geo_device(raw: Row) -> NormalizeResult:
    if MALFORMED_LINE_KEY in raw:
        return None, [f"malformed line, wrong column count: {raw[MALFORMED_LINE_KEY]!r}"], []

    selected, extra_fields = _select_known_fields(raw, GEO_DEVICE_FIELDS)
    if _is_blank_row(selected):
        return None, [], extra_fields
    if _is_duplicate_header_row(selected):
        return None, [], extra_fields

    row = {
        "geo_device_id": _clean_str_field(selected.get("geo_device_id")),
        # collapse_nulls=False: a literal "NA" must survive as-is so
        # validators.py's region check can catch the NA/NAM ambiguity
        # explicitly, instead of it silently becoming an empty string here.
        "region": _clean_str_field(selected.get("region"), collapse_nulls=False).upper(),
        "country": _clean_str_field(selected.get("country")),
        "device_model": _clean_str_field(selected.get("device_model")),
        "os_version": _clean_str_field(selected.get("os_version")),
    }
    return row, [], extra_fields


NORMALIZE_BY_ENTITY = {
    "ad_events": normalize_ad_event,
    "apps": normalize_app,
    "advertisers": normalize_advertiser,
    "geo_device": normalize_geo_device,
}


def normalize(entity: str, raw: Row) -> NormalizeResult:
    fn = NORMALIZE_BY_ENTITY.get(entity)
    if fn is None:
        raise ValueError(f"unknown entity '{entity}'")
    return fn(raw)
