import unittest

from api import server
from ui.bundle import load
from ui.llm import _answer_from_bundle


FIXTURE = "tests/e2e/results/bundle_rca_t3_final.json"


class IncidentRegressionTests(unittest.TestCase):
    def test_string_headline_supports_deterministic_fallback(self):
        bundle = load(path=FIXTURE, incident="INC-1")
        answer = _answer_from_bundle(bundle, "why did it drop?")
        self.assertIn("fill_rate moved", answer)

    def test_inc_zero_resolves_to_first_incident(self):
        bundle = load(path=FIXTURE, incident="INC-0")
        self.assertEqual(bundle["id"], "inv_fill_rate_2026-06-15")

    def test_short_incident_id_resolves_in_api(self):
        server._cache["test"] = {
            "investigations": [{"id": "engine-1", "metric": "fill_rate"}]
        }
        self.assertEqual(
            server.investigation("INC-1", db="test")["id"],
            "engine-1",
        )


if __name__ == "__main__":
    unittest.main()
