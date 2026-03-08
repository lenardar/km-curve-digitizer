"""Provider parsing and request-shaping tests."""

from __future__ import annotations

import base64
import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from pykmextract.providers.vision import (
    OpenAICompatibleVisionProvider,
    _extract_json_block,
)


class _FakeHTTPResponse:
    def __init__(self, payload: dict):
        self._payload = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class ProviderTests(unittest.TestCase):
    def test_extract_json_block_accepts_fenced_json(self):
        payload = _extract_json_block("```json\n{\"n_curves\": 2}\n```")
        self.assertEqual(payload, {"n_curves": 2})

    def test_openai_compatible_provider_posts_image_and_parses_response(self):
        with TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "tiny.png"
            image_path.write_bytes(
                base64.b64decode(
                    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9VE3FoAAAAAASUVORK5CYII="
                )
            )

            captured = {}

            def fake_urlopen(req, timeout=0):
                captured["url"] = req.full_url
                captured["headers"] = dict(req.header_items())
                captured["body"] = json.loads(req.data.decode("utf-8"))
                return _FakeHTTPResponse(
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": "```json\n{\"n_curves\": 2, \"x_axis\": {\"min\": 0, \"max\": 24, \"unit\": \"months\", \"label\": \"Time\"}, \"y_axis\": {\"min\": 0, \"max\": 1, \"is_percentage\": false, \"label\": \"Survival\"}, \"curves\": [{\"id\": 1, \"legend_name\": \"A\", \"color_description\": \"blue\", \"rgb_approx\": [1, 2, 3], \"line_style\": \"solid\"}, {\"id\": 2, \"legend_name\": \"B\", \"color_description\": \"red\", \"rgb_approx\": [4, 5, 6], \"line_style\": \"solid\"}], \"at_risk_table\": {\"time_points\": [], \"counts_by_curve\": []}, \"total_events_by_curve\": [null, null], \"has_confidence_interval\": false, \"has_censoring_marks\": false, \"confidence\": {\"overall\": \"medium\", \"at_risk_table\": \"low\", \"color_identification\": \"medium\"}, \"notes\": \"\"}\n```"
                                }
                            }
                        ]
                    }
                )

            provider = OpenAICompatibleVisionProvider(
                base_url="https://example.test/v1",
                api_key="secret",
                default_model="qwen-vl-plus",
            )

            with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
                result = provider.extract_semantics(str(image_path), prompt="extract")

            self.assertEqual(result["n_curves"], 2)
            self.assertEqual(captured["url"], "https://example.test/v1/chat/completions")
            self.assertEqual(captured["body"]["model"], "qwen-vl-plus")
            self.assertEqual(captured["body"]["messages"][0]["content"][0]["text"], "extract")
            image_url = captured["body"]["messages"][0]["content"][1]["image_url"]["url"]
            self.assertTrue(image_url.startswith("data:image/png;base64,"))


if __name__ == "__main__":
    unittest.main()
