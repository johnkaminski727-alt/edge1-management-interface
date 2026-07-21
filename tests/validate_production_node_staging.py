#!/usr/bin/env python3
import json
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "deploy/production-node/validate-manifest.py"
MANIFEST = ROOT / "config/production-node/node-manifest.example.json"


class ProductionNodeStagingTests(unittest.TestCase):
    def run_validator(self, path):
        return subprocess.run(["python3", str(VALIDATOR), str(path)], text=True, capture_output=True)

    def test_example_manifest_is_safe(self):
        result = self.run_validator(MANIFEST)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertTrue(all(value is False for value in data["safety"].values()))

    def test_traffic_enablement_is_rejected(self):
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
        data["safety"]["production_traffic_enabled"] = True
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "unsafe.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            result = self.run_validator(path)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("production_traffic_enabled", result.stderr)


if __name__ == "__main__":
    unittest.main()
