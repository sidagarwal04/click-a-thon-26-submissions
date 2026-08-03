from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

ALERT = {
    "title": "fill_rate anomaly",
    "body": "z=12.3",
    "link": "https://example.com/d/1",
}


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_accepts_and_dedups_alert():
    first = client.post("/webhooks/alerts", json=ALERT)
    assert first.status_code == 202
    assert first.json()["status"] == "accepted"

    second = client.post("/webhooks/alerts", json=ALERT)
    assert second.status_code == 202
    assert second.json()["status"] == "duplicate"

    different = client.post("/webhooks/alerts", json={**ALERT, "body": "z=99.9"})
    assert different.json()["status"] == "accepted"


def test_alert_without_metric_id_skips_investigation():
    resp = client.post("/webhooks/alerts", json={**ALERT, "body": "no metric here"})
    assert resp.json()["investigation"] == "skipped"


def test_unknown_metric_id_skips_investigation():
    with patch("app.main.get_metric", return_value=None) as mocked:
        resp = client.post(
            "/webhooks/alerts", json={**ALERT, "body": "metric_id=not_real"}
        )
    mocked.assert_called_once_with("not_real")
    assert resp.json()["investigation"] == "unknown_metric"


def test_known_metric_id_starts_investigation():
    with (
        patch("app.main.get_metric", return_value={"metric_id": "fill_rate"}),
        patch(
            "app.main.run_investigation",
            return_value={"metric_id": "fill_rate", "verdict": "not_reproducible"},
        ) as mocked_investigate,
        patch("app.main.narrate", return_value={"narrative": "stub", "grounded": True}),
    ):
        resp = client.post(
            "/webhooks/alerts", json={**ALERT, "body": "metric_id=fill_rate"}
        )
    assert resp.json() == {
        "status": "accepted",
        "delivery_key": resp.json()["delivery_key"],
        "investigation": "started",
        "metric_id": "fill_rate",
        "dimension_id": None,
    }
    mocked_investigate.assert_called_once_with("fill_rate", None)


def test_optional_dimension_id_is_passed_through_as_a_hint():
    with (
        patch("app.main.get_metric", return_value={"metric_id": "fill_rate"}),
        patch(
            "app.main.run_investigation",
            return_value={"metric_id": "fill_rate", "verdict": "not_reproducible"},
        ) as mocked_investigate,
        patch("app.main.narrate", return_value={"narrative": "stub", "grounded": True}),
    ):
        resp = client.post(
            "/webhooks/alerts",
            json={**ALERT, "body": "metric_id=fill_rate dimension_id=os_version"},
        )
    assert resp.json()["dimension_id"] == "os_version"
    mocked_investigate.assert_called_once_with("fill_rate", "os_version")


SERIES_WINDOW = {"start": "2026-07-30T00:00:00", "end": "2026-07-31T00:00:00"}


def test_global_series_unknown_metric_returns_404():
    with patch("app.main.get_metric", return_value=None):
        resp = client.post(
            "/internal/global-series", json={"metric_id": "not_real", **SERIES_WINDOW}
        )
    assert resp.status_code == 404


def test_global_series_known_metric_returns_reproduce_global_rows():
    rows = [
        {
            "ts": "2026-07-30T09:00:00",
            "actual": 0.75,
            "expected": 0.78,
            "z_score": -4.1,
            "delta_rel": -0.03,
            "is_anomaly": 1,
        }
    ]
    with (
        patch("app.main.get_metric", return_value={"metric_id": "fill_rate"}),
        patch("app.main.reproduce_global", return_value=rows) as mocked,
    ):
        resp = client.post(
            "/internal/global-series", json={"metric_id": "fill_rate", **SERIES_WINDOW}
        )
    assert resp.json() == rows
    assert mocked.call_args[0][0] == "fill_rate"


def test_global_series_nan_from_insufficient_baseline_becomes_json_null():
    # a bucket without MIN_BASE_POINTS worth of history yet has expected/z_score = NaN —
    # Starlette's JSONResponse 500s on a raw NaN, so this must come back as null, not crash.
    rows = [
        {
            "ts": "2026-07-30T09:00:00",
            "actual": 7769.0,
            "expected": float("nan"),
            "z_score": float("nan"),
            "delta_rel": float("nan"),
            "is_anomaly": 0,
        }
    ]
    with (
        patch("app.main.get_metric", return_value={"metric_id": "requests"}),
        patch("app.main.reproduce_global", return_value=rows),
    ):
        resp = client.post(
            "/internal/global-series", json={"metric_id": "requests", **SERIES_WINDOW}
        )
    assert resp.status_code == 200
    assert resp.json() == [
        {
            "ts": "2026-07-30T09:00:00",
            "actual": 7769.0,
            "expected": None,
            "z_score": None,
            "delta_rel": None,
            "is_anomaly": 0,
        }
    ]


def test_segment_series_unknown_metric_returns_404():
    with patch("app.main.get_metric", return_value=None):
        resp = client.post(
            "/internal/segment-series",
            json={"metric_id": "not_real", "dim_name": "os_version", **SERIES_WINDOW},
        )
    assert resp.status_code == 404


def test_segment_series_invalid_dim_name_returns_400():
    with (
        patch("app.main.get_metric", return_value={"metric_id": "fill_rate"}),
        patch(
            "app.main.reproduce_segment",
            side_effect=ValueError("unknown dimension column 'nope'"),
        ),
    ):
        resp = client.post(
            "/internal/segment-series",
            json={"metric_id": "fill_rate", "dim_name": "nope", **SERIES_WINDOW},
        )
    assert resp.status_code == 400


def test_segment_series_filters_to_requested_dim_values():
    rows = [
        {
            "ts": "2026-07-30T09:00:00",
            "dim_value": "Android 15",
            "actual": 0.43,
            "expected": 0.74,
        },
        {
            "ts": "2026-07-30T09:00:00",
            "dim_value": "Android 14",
            "actual": 0.77,
            "expected": 0.78,
        },
    ]
    with (
        patch("app.main.get_metric", return_value={"metric_id": "fill_rate"}),
        patch("app.main.reproduce_segment", return_value=rows),
    ):
        resp = client.post(
            "/internal/segment-series",
            json={
                "metric_id": "fill_rate",
                "dim_name": "os_version",
                "dim_values": ["Android 15"],
                **SERIES_WINDOW,
            },
        )
    assert [r["dim_value"] for r in resp.json()] == ["Android 15"]
