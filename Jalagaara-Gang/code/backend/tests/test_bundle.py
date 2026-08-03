"""Guards the contract: the fixture must validate, and the guardrail must catch fabrication."""
import json
from pathlib import Path

import jsonschema

from models import EvidenceBundle
from narrator.guardrail import verify

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "contracts" / "evidence_bundle.schema.json").read_text())
FIXTURE = json.loads((ROOT / "fixtures" / "sample_bundle.json").read_text())


def test_fixture_matches_json_schema():
    jsonschema.validate(FIXTURE, SCHEMA)


def test_fixture_parses_into_model():
    EvidenceBundle.model_validate(FIXTURE)


def test_guardrail_passes_on_fixture_narrative():
    bundle = EvidenceBundle.model_validate(FIXTURE)
    assert verify(bundle, bundle.narrative).passed


def test_guardrail_flags_fabricated_number():
    bundle = EvidenceBundle.model_validate(FIXTURE)
    result = verify(bundle, "Revenue fell because of 999888 phantom clicks.")
    assert not result.passed
    assert "999888" in result.unverified_numbers
