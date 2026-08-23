import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

import ava_visual_generator as visual
import ava_visual_worker as worker


class VisualGeneratorTests(unittest.TestCase):
    def test_clipart_prompt_adds_transparent_asset_instruction(self):
        text = visual._prompt("clipart", "a blue telephone")
        self.assertIn("transparent background", text)
        self.assertIn("a blue telephone", text)

    def test_diagram_prompt_adds_legibility_instruction(self):
        text = visual._prompt("diagram", "PBX to carrier call flow")
        self.assertIn("legible labels", text)
        self.assertIn("PBX to carrier call flow", text)

    def test_signed_asset_url_is_fail_closed(self):
        with self.assertRaises(visual.VisualError):
            visual._wwcx_headers("GET", "https://example.com/api/ava-visual-asset.php", b"", "x" * 32, "kid")

    def test_process_visual_requires_scope(self):
        payload = {
            "request_id": "a" * 32,
            "user": {"id": "b" * 64, "scopes": ["chat:general"]},
            "message": "make a picture",
            "visual_request": {"mode": "image", "size": "1024x1024"},
        }
        with self.assertRaisesRegex(visual.VisualError, "visual:create"):
            visual.process_visual(payload, "s" * 32, "kid")

    def test_edit_requires_edit_scope(self):
        payload = {
            "request_id": "a" * 32,
            "user": {"id": "b" * 64, "scopes": ["visual:create"]},
            "message": "remove the background",
            "visual_request": {"mode": "edit", "size": "1024x1024", "source_kind": "visual", "source_id": "vis_" + "c" * 16},
        }
        with self.assertRaisesRegex(visual.VisualError, "visual:edit"):
            visual.process_visual(payload, "s" * 32, "kid")

    def test_worker_claims_visual_lane(self):
        calls = []
        def fake_queue(payload, secret, key):
            calls.append(payload)
            return {"status": "idle", "poll_after_ms": 2000}
        with patch.object(worker, "queue_call", side_effect=fake_queue):
            delay = worker.process_once("s" * 32, "kid")
        self.assertEqual(calls[0]["action"], "claim_visual")
        self.assertEqual(delay, 2.0)

    def test_worker_completes_visual_result(self):
        request_id = "a" * 32
        payload = {"request_id": request_id}
        calls = []
        def fake_queue(body, secret, key):
            calls.append(body)
            if body["action"] == "claim_visual":
                return {"status": "job", "request_id": request_id, "gateway_request": payload}
            return {"status": "accepted", "request_id": request_id}
        with patch.object(worker, "queue_call", side_effect=fake_queue), patch.object(worker, "process_visual", return_value={"request_id": request_id, "answer": "done", "visuals": []}):
            worker.process_once("s" * 32, "kid")
        self.assertEqual(calls[-1]["action"], "complete")
        self.assertEqual(calls[-1]["outcome"], "completed")


if __name__ == "__main__":
    unittest.main()
