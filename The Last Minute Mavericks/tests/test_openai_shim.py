from __future__ import annotations

import os
import json
import tempfile
import time
import unittest
from unittest.mock import patch
from pathlib import Path

from integrations import openai_shim
from ui import incidents


class OpenAIShimTests(unittest.TestCase):
    def test_shim_loads_current_api_bundle_after_refresh(self):
        current = {
            "investigations": [
                {"id": "new", "headline": {"delta_pct": -42}, "diagnosis": "current"}
            ]
        }
        old_cache = dict(incidents._api_cache)
        incidents._api_cache.update(t=time.time(), doc={"stale": True}, base="api")
        seen_cache = []

        def api_doc():
            seen_cache.append(dict(incidents._api_cache))
            return current

        try:
            with patch.dict(os.environ, {"RCOS_BUNDLE": "", "RCOS_INCIDENT": ""}, clear=False):
                with patch.object(incidents, "_api_doc", api_doc):
                    bundle = openai_shim._load_bundle("0")
        finally:
            incidents._api_cache.update(old_cache)

        self.assertEqual(bundle["id"], "new")
        self.assertEqual(seen_cache, [{"t": 0.0, "doc": None, "base": "api"}])

    def test_explicit_bundle_override_skips_api_fetch(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bundle.json"
            path.write_text(json.dumps({"diagnosis": "fixture"}))
            with patch.dict(os.environ, {"RCOS_BUNDLE": str(path)}, clear=False):
                with patch.object(incidents, "_api_doc", side_effect=AssertionError):
                    bundle = openai_shim._load_bundle()

        self.assertEqual(bundle["diagnosis"], "fixture")
