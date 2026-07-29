#!/usr/bin/env python3
import importlib.util
import json
import pathlib
import tempfile
import unittest

MODULE_PATH = pathlib.Path(__file__).parents[1] / "server" / "security_operations_exporter.py"
SPEC = importlib.util.spec_from_file_location("security_operations_exporter", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class SecurityOperationsExporterCacheTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        root = pathlib.Path(self.tempdir.name)
        self.source = root / "latest.json"
        self.output = root / "security-operations.json"
        self.original_source = MODULE.SOURCE
        self.original_output = MODULE.OUTPUT
        MODULE.SOURCE = self.source
        MODULE.OUTPUT = self.output

    def tearDown(self):
        MODULE.SOURCE = self.original_source
        MODULE.OUTPUT = self.original_output
        self.tempdir.cleanup()

    def write_live_source(self):
        self.source.write_text(json.dumps({
            "generated_at": "2026-07-29T06:00:00+00:00",
            "security": {
                "available": True,
                "health": {"status": "healthy", "warnings": []},
                "recent_alerts": [{"signature": f"alert-{index}"} for index in range(60)],
            },
        }), encoding="utf-8")

    def test_live_snapshot_is_marked_live_and_bounded(self):
        self.write_live_source()
        snapshot = MODULE.live_snapshot()
        self.assertEqual(snapshot["cache"]["mode"], "live")
        self.assertFalse(snapshot["cache"]["stale"])
        self.assertEqual(len(snapshot["recent_alerts"]), 50)

    def test_fallback_reuses_last_known_good_snapshot(self):
        self.write_live_source()
        live = MODULE.live_snapshot()
        MODULE.write_snapshot(live)
        self.source.unlink()
        fallback = MODULE.fallback_snapshot(FileNotFoundError("collector unavailable"))
        self.assertTrue(fallback["available"])
        self.assertEqual(fallback["cache"]["mode"], "last_known_good")
        self.assertTrue(fallback["cache"]["stale"])
        self.assertIn("collector unavailable", fallback["cache"]["source_error"])
        self.assertEqual(len(fallback["recent_alerts"]), 50)

    def test_repeated_fallback_does_not_duplicate_warning(self):
        self.write_live_source()
        MODULE.write_snapshot(MODULE.live_snapshot())
        first = MODULE.fallback_snapshot(FileNotFoundError("collector unavailable"))
        MODULE.write_snapshot(first)
        second = MODULE.fallback_snapshot(FileNotFoundError("collector still unavailable"))
        warnings = second["health"]["warnings"]
        self.assertEqual(warnings.count(MODULE.CACHE_WARNING), 1)

    def test_missing_cache_reports_unavailable(self):
        fallback = MODULE.fallback_snapshot(FileNotFoundError("collector unavailable"))
        self.assertFalse(fallback["available"])
        self.assertEqual(fallback["cache"]["mode"], "unavailable")
        self.assertTrue(fallback["cache"]["stale"])


if __name__ == "__main__":
    unittest.main()
