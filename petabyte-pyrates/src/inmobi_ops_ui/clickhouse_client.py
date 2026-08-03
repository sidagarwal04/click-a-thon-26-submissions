"""ClickHouse HTTP client for the ops console."""

from __future__ import annotations

import base64
import json
import os
import re
import urllib.error
import urllib.request
from typing import Any

UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


class ClickHouseError(RuntimeError):
    """Raised when a ClickHouse query fails."""


def _config() -> tuple[str, str, str]:
    host = os.environ.get("CLICKHOUSE_HOST", "").strip()
    user = os.environ.get("CLICKHOUSE_USER", "default").strip() or "default"
    password = os.environ.get("CLICKHOUSE_PASSWORD", "")
    if not host:
        raise ClickHouseError("Set CLICKHOUSE_HOST in .env")
    return host, user, password


def query_json(sql: str) -> list[dict[str, Any]]:
    host, user, password = _config()
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    body = f"{sql}\nFORMAT JSONEachRow"
    request = urllib.request.Request(
        f"https://{host}:8443/",
        data=body.encode(),
        headers={
            "Authorization": f"Basic {token}",
            "Content-Type": "text/plain; charset=utf-8",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            text = response.read().decode()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise ClickHouseError(f"ClickHouse HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise ClickHouseError(f"ClickHouse connection failed: {exc.reason}") from exc

    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def fetch_incidents(limit: int = 200) -> list[dict[str, Any]]:
    return query_json(
        f"""
        SELECT
            toString(anomaly_id) AS anomaly_id,
            detected_at,
            metric_hour,
            region,
            ad_format,
            slice_type,
            slice_value,
            metric_name,
            current_value,
            baseline_value,
            delta_pct,
            z_score,
            volume_requests,
            direction,
            severity,
            detection_tier,
            confidence_tier,
            detection_methods,
            status,
            disposition,
            investigated_at,
            if(length(rca_description) > 0, 1, 0) AS has_rca,
            substring(rca_description, 1, 280) AS rca_preview,
            if(length(last_error) > 0, 1, 0) AS has_error
        FROM gold.metric_anomalies
        ORDER BY
            metric_hour DESC,
            multiIf(
                severity = 'critical', 4,
                severity = 'high', 3,
                severity = 'medium', 2,
                1
            ) DESC,
            detected_at DESC
        LIMIT {int(limit)}
        """
    )


def fetch_incident(anomaly_id: str) -> dict[str, Any] | None:
    if not UUID_RE.match(anomaly_id):
        raise ClickHouseError("Invalid anomaly_id")
    rows = query_json(
        f"""
        SELECT
            toString(anomaly_id) AS anomaly_id,
            detected_at,
            metric_hour,
            segment_key,
            region,
            ad_format,
            slice_type,
            slice_value,
            metric_name,
            current_value,
            baseline_value,
            delta_pct,
            z_score,
            volume_requests,
            direction,
            severity,
            detection_tier,
            confidence_tier,
            detection_methods,
            status,
            disposition,
            investigated_at,
            last_error,
            rca_description,
            evidence_json
        FROM gold.metric_anomalies
        WHERE anomaly_id = '{anomaly_id.lower()}'
        LIMIT 1
        """
    )
    return rows[0] if rows else None


def fetch_stats() -> dict[str, Any]:
    rows = query_json(
        """
        SELECT
            count() AS total,
            countIf(status = 'open') AS open_count,
            countIf(status = 'closed') AS closed_count,
            countIf(disposition = 'pending') AS pending_disposition,
            countIf(disposition = 'confirmed') AS confirmed_count,
            countIf(disposition = 'false_positive') AS false_positive_count,
            countIf(disposition = 'inconclusive') AS inconclusive_count,
            countIf(length(rca_description) > 0) AS with_rca,
            countIf(length(last_error) > 0) AS with_errors,
            max(metric_hour) AS latest_metric_hour
        FROM gold.metric_anomalies
        """
    )
    return rows[0] if rows else {}
