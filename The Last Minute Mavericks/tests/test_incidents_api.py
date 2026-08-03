import unittest
from unittest.mock import patch

from ui import incidents


class IncidentApiTests(unittest.TestCase):
    def test_normalize_api_preserves_zero_and_trace_fallback(self):
        raw = {
            "scan_summary": {
                "real_incidents": 0,
                "incidents_found": 4,
                "trace_url": "https://trace.example/scan",
            },
            "investigations": [
                {
                    "id": "engine-1",
                    "metric": "fill_rate",
                    "window": ["2026-06-28", "2026-06-30"],
                    "verdict": "LOCALIZED_2D",
                    "culprit": {
                        "dimension": "region×os_version",
                        "segment": "region=APAC × os_version=iOS 18.1",
                    },
                }
            ],
        }
        with patch.object(incidents, "_api_base", return_value="http://engine"):
            doc = incidents._normalize_api(raw)

        self.assertEqual(doc["scan_summary"]["incidents_found"], 0)
        self.assertEqual(doc["scan_summary"]["trace_url"], raw["scan_summary"]["trace_url"])
        self.assertEqual(doc["investigations"][0]["trace_url"], raw["scan_summary"]["trace_url"])

    def test_display_snapshot_humanizes_two_dimensional_static_cause(self):
        card = {
            "panes": ["fill_rate"],
            "diagnosis": {
                "cause": "region×os_version = region=APAC × os_version=iOS 18.1"
            },
        }
        display = incidents.display_snapshot(card, "05 Jul 2026, 23:59")

        self.assertEqual(display["metric"], "Fill rate")
        self.assertIn("APAC", display["where"])
        self.assertIn("iOS 18.1", display["where"])
        self.assertEqual(display["data_through"], "05 Jul 2026, 23:59")


if __name__ == "__main__":
    unittest.main()
