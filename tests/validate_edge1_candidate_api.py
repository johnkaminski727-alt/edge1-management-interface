#!/usr/bin/env python3
"""G2 loopback API integration regressions; ephemeral port, temp files only."""
from __future__ import annotations
import json
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest

TOOL = Path(__file__).resolve().parents[1] / "tools/operations"
sys.path.insert(0, str(TOOL))
from edge1_candidate_store import CandidateStore
from edge1_candidate_api import LocalHTTPServer, read_observation

TOKEN = "a" * 64


class CandidateAPITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.ui = root / "index.html"
        self.ui.write_text("<!doctype html><title>test only</title>")
        self.observation = root / "core-status.json"
        self.store = CandidateStore(root / "candidate.sqlite")
        self.server = LocalHTTPServer(("127.0.0.1", 0), self.ui, self.store, TOKEN, self.observation)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.port = self.server.server_port
        self.base = "http://127.0.0.1:" + str(self.port)

    def call(self, path, body=None, token=TOKEN, origin=None, host=None):
        headers = {"X-Edge1-Token": token}
        if host is not None:
            headers["Host"] = host
        if body is not None:
            headers["Content-Type"] = "application/json"
            headers["Origin"] = origin if origin is not None else self.base
            payload = json.dumps(body).encode()
        else:
            payload = None
        request = urllib.request.Request(self.base + path, data=payload, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=3) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read())

    def test_authentication_host_and_origin(self):
        self.assertEqual(self.call("/api/state", token="wrong")[0], 401)
        self.assertEqual(self.call("/api/state", host="evil.example")[0], 403)
        state = self.call("/api/state")[1]
        self.assertFalse(state["pending"])
        payload = {"expected_candidate_revision": state["candidate_revision"],
                   "section": "alerts", "field": "max_items", "value": 5}
        self.assertEqual(self.call("/api/propose", payload, origin="https://evil.example")[0], 403)
        self.assertEqual(self.call("/api/propose", payload, token="wrong")[0], 401)
        self.assertEqual(self.call("/api/state")[1]["candidate"]["alerts"]["max_items"], 20)

    def test_save_restart_discard_and_conflict(self):
        first = self.call("/api/state")[1]
        request = {"expected_candidate_revision": first["candidate_revision"],
                   "section": "dashboard", "field": "refresh_seconds", "value": 60}
        code, after = self.call("/api/propose", request)
        self.assertEqual(code, 200)
        self.assertTrue(after["pending"])
        self.assertEqual(CandidateStore(self.store.path).read()["candidate"]["dashboard"]["refresh_seconds"], 60)
        self.assertEqual(self.call("/api/propose", request)[0], 409)
        audit = self.call("/api/audit")[1]["events"]
        self.assertEqual(len(audit), 1)
        self.assertEqual(self.call("/api/discard", {"expected_candidate_revision": after["candidate_revision"]})[0], 200)
        self.assertFalse(self.call("/api/state")[1]["pending"])

    def test_invalid_and_no_apply_endpoint(self):
        old = self.call("/api/state")[1]
        bad = {"expected_candidate_revision": old["candidate_revision"],
               "section": "network", "field": "firewall", "value": "disabled"}
        self.assertEqual(self.call("/api/propose", bad)[0], 422)
        self.assertEqual(self.call("/api/apply", bad)[0], 404)
        self.assertEqual(self.call("/api/state")[1]["candidate_revision"], old["candidate_revision"])
        self.assertEqual(self.call("/api/audit")[1]["events"], [])

    def test_fresh_and_stale_observation_without_leaking_services(self):
        now = datetime.now(timezone.utc)
        example = {"schema_version": "wwcx.core-observation.v1",
                   "read_only": True, "generated_at": now.isoformat(),
                   "services": {"ssh": {"state": "active", "password": "do-not-export"},
                                "unbound": {"state": "failed"}}}
        self.observation.write_text(json.dumps(example))
        status, obs = self.call("/api/observation")
        self.assertEqual(status, 200)
        self.assertTrue(obs["fresh"])
        self.assertEqual(obs["active_service_count"], 1)
        self.assertNotIn("do-not-export", json.dumps(obs))
        example["generated_at"] = (now - timedelta(hours=1)).isoformat()
        self.observation.write_text(json.dumps(example))
        self.assertFalse(self.call("/api/observation")[1]["fresh"])
        self.observation.unlink()
        self.assertFalse(self.call("/api/observation")[1]["available"])


if __name__ == "__main__":
    unittest.main()
