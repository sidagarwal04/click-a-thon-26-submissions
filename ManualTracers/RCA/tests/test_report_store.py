import json

from app.report_store import persist_report

REPORT = {
    "id": "rca-fill_rate-abcd1234",
    "status": "localized",
    "trigger": {"metric_id": "fill_rate"},
}


def test_persist_report_writes_one_json_file_named_by_id(tmp_path):
    path = persist_report(REPORT, directory=tmp_path)

    assert path == tmp_path / "rca-fill_rate-abcd1234.json"
    assert json.loads(path.read_text()) == REPORT


def test_persist_report_creates_the_directory_if_missing(tmp_path):
    target = tmp_path / "nested" / "reports"
    persist_report(REPORT, directory=target)

    assert (target / "rca-fill_rate-abcd1234.json").exists()
