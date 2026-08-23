import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "server" / "bigbird_ops_collect.py"


def load_collector():
    spec = importlib.util.spec_from_file_location("bigbird_ops_collect_office_test", MODULE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class BigBirdOfficePortabilitySnapshotTests(unittest.TestCase):
    def stub_expensive_collectors(self, collector):
        collector.service = lambda name: {"name": name, "active": "test"}
        collector.firewall = lambda: {"available": True}
        collector.unbound = lambda: {"available": True}
        collector.wireguard = lambda: {"available": True}
        collector.suricata = lambda: {"available": True, "privacy": {"packet_payloads_included": False, "raw_events_included": False}}
        collector.automation = lambda: {"timers": []}
        collector.logs = lambda: {}
        collector.watched_paths = lambda: []

    def test_extension_fields_are_aggregate_and_locked(self):
        collector = load_collector()
        self.stub_expensive_collectors(collector)
        collector.build_office_portability_summary = lambda: {
            "ava_office": {
                "available": True,
                "mode": "read-only",
                "execution_enabled": False,
                "work_items": {"needs_owner": 2},
                "actions": {"awaiting_confirmation": 1},
                "standing_instructions": 3,
            },
            "number_portability": {
                "available": True,
                "mode": "read-only",
                "cases": {"ready_for_review": 1},
                "numbers": 4,
                "documents": 2,
                "submission_authorized": False,
                "cutover_authorized": False,
            },
            "privacy": {
                "record_level_content_included": False,
                "telephone_numbers_included": False,
                "transcripts_or_audio_included": False,
                "document_references_included": False,
                "credentials_included": False,
            },
        }
        snapshot = collector.build_snapshot()
        self.assertEqual(snapshot["format"], "project-big-bird-operations-center-v1")
        self.assertEqual(snapshot["project_version"], "4.0.5")
        self.assertFalse(snapshot["ava_office"]["execution_enabled"])
        self.assertFalse(snapshot["number_portability"]["submission_authorized"])
        self.assertFalse(snapshot["number_portability"]["cutover_authorized"])
        self.assertFalse(snapshot["office_services_privacy"]["telephone_numbers_included"])

    def test_missing_extension_fails_closed_without_breaking_snapshot(self):
        collector = load_collector()
        self.stub_expensive_collectors(collector)
        collector.build_office_portability_summary = None
        snapshot = collector.build_snapshot()
        self.assertFalse(snapshot["ava_office"]["available"])
        self.assertFalse(snapshot["ava_office"]["execution_enabled"])
        self.assertFalse(snapshot["number_portability"]["available"])
        self.assertFalse(snapshot["number_portability"]["submission_authorized"])
        self.assertFalse(snapshot["number_portability"]["cutover_authorized"])


if __name__ == "__main__":
    unittest.main()
