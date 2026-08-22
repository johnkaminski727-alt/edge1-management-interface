import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "server"))
import cookie_monster_contract as contract
import cookie_monster_review as review
import cookie_monster_fengus_worker as worker


class ContractTests(unittest.TestCase):
    def test_job_request_is_deterministic_and_path_free(self):
        one = contract.make_request("synthetic-media-v1", "bigbird")
        two = contract.make_request("synthetic-media-v1", "bigbird")
        self.assertEqual(one["job_id"], two["job_id"])
        self.assertEqual(one["idempotency_key"], two["idempotency_key"])
        encoded = json.dumps(one).lower()
        self.assertNotIn("/srv/", encoded)
        self.assertNotIn("http", encoded)

    def test_job_contract_rejects_unexpected_path_field(self):
        value = contract.make_request("synthetic-media-v1", "bigbird")
        value["source_path"] = "/srv/archive"
        with self.assertRaises(contract.ContractError):
            contract.validate(value)


class ReviewTests(unittest.TestCase):
    def _records(self):
        return [{
            "knowledge_record_id": "kr-" + "a" * 32,
            "source_asset_id": "sha256:" + "b" * 64,
            "source_asset_location": "sample.wav",
            "review_status": "draft",
        }]

    def test_review_state_machine_is_append_only(self):
        records = self._records()
        decisions = []
        submit = review.make_decision(records, decisions, records[0]["knowledge_record_id"], "pending_review", "operator", "ready for review", timestamp="2026-08-22T08:00:00Z")
        decisions.append(submit)
        approve = review.make_decision(records, decisions, records[0]["knowledge_record_id"], "approved", "operator", "provenance verified", timestamp="2026-08-22T08:01:00Z")
        decisions.append(approve)
        self.assertEqual(approve["previous_decision_hash"], submit["decision_hash"])
        state = review.build_review_snapshot(records, decisions)
        self.assertEqual(state["summary"]["approved"], 1)
        with self.assertRaises(review.ReviewError):
            review.make_decision(records, decisions, records[0]["knowledge_record_id"], "rejected", "operator", "cannot change terminal state")

    def test_review_event_is_physically_appended(self):
        with tempfile.TemporaryDirectory() as td:
            path = pathlib.Path(td) / "review-decisions.jsonl"
            records = self._records()
            first = review.make_decision(records, [], records[0]["knowledge_record_id"], "pending_review", "operator", "queue it", timestamp="2026-08-22T08:00:00Z")
            review.append_event(path, first)
            before = path.read_bytes()
            second = review.make_decision(records, [first], records[0]["knowledge_record_id"], "approved", "operator", "looks good", timestamp="2026-08-22T08:01:00Z")
            review.append_event(path, second)
            self.assertTrue(path.read_bytes().startswith(before))
            self.assertEqual(len(review.read_jsonl(path)), 2)


class FengusTests(unittest.TestCase):
    def _request(self, operation="text.token-stats"):
        return {
            "schema": worker.SCHEMA,
            "job_id": "cmjob-" + "1" * 24,
            "work_id": "work-" + "2" * 24,
            "operation": operation,
            "source_asset_id": "sha256:" + "3" * 64,
            "payload": {"text": "eats ASCII for brunch\n"},
        }

    def test_worker_executes_only_allowlisted_data_operation(self):
        result = worker.execute(self._request())
        self.assertEqual(result["output"]["words"], 4)
        self.assertTrue(result["result_hash"].startswith("sha256:"))

    def test_worker_rejects_archive_paths_and_commands(self):
        request = self._request()
        request["payload"] = {"path": "/srv/archive/thing", "command": "cat /etc/passwd"}
        with self.assertRaises(worker.WorkerError):
            worker.execute(request)

    def test_worker_unit_has_os_isolation_boundaries(self):
        text = (ROOT / "deploy" / "cookie-monster-fengus-worker@.service").read_text(encoding="utf-8")
        for required in (
            "PrivateNetwork=yes",
            "ProtectSystem=strict",
            "NoNewPrivileges=yes",
            "InaccessiblePaths=/srv/cookie-monster /var/lib/cookie-monster-alpha/generated",
            "MemoryMax=256M",
            "TimeoutStartSec=30s",
        ):
            self.assertIn(required, text)


class UiTests(unittest.TestCase):
    def test_operator_ui_keeps_mascot_and_exposes_m3_m4_surfaces(self):
        text = (ROOT / "src" / "web" / "cookie-monster" / "index.html").read_text(encoding="utf-8")
        self.assertIn("assets/mascot.webp", text)
        self.assertIn("Needs human eyes", text)
        self.assertIn("Big Bird jobs", text)
        self.assertIn("Fengus worker", text)
        self.assertIn("data-review-record", text)
        self.assertIn("authenticated-operator", text)
        self.assertNotIn("fetch('/approve'", text)


if __name__ == "__main__":
    unittest.main()
