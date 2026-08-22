import json
import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "server"))
import cookie_monster_contract as contract
import cookie_monster_dispatch as dispatch


class DispatchTests(unittest.TestCase):
    def layout(self, root):
        dataset_root = root / "datasets"
        dataset_root.mkdir()
        source = dataset_root / "alpha-staging"
        source.mkdir()
        (source / "one.txt").write_text("hello\n", encoding="utf-8")
        output_root = root / "generated"
        output_root.mkdir()
        registry = {
            "schema": dispatch.REGISTRY_SCHEMA,
            "datasets": {
                "alpha-staging": {
                    "enabled": True,
                    "non_production": True,
                    "read_only": True,
                    "description": "test",
                }
            },
        }
        job = contract.make_request("alpha-staging", "tester")
        return dataset_root, output_root, registry, job

    def test_resolve_requires_registered_nonproduction_readonly_dataset(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            dataset_root, _output, registry, _job = self.layout(root)
            self.assertEqual(
                dispatch.resolve_dataset(registry, dataset_root, "alpha-staging"),
                (dataset_root / "alpha-staging").resolve(),
            )
            for key in ("enabled", "non_production", "read_only"):
                bad = json.loads(json.dumps(registry))
                bad["datasets"]["alpha-staging"][key] = False
                with self.assertRaises(dispatch.DispatchError):
                    dispatch.resolve_dataset(bad, dataset_root, "alpha-staging")

    def test_symlink_dataset_is_rejected(self):
        if not hasattr(os, "symlink"):
            self.skipTest("symlink unavailable")
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            dataset_root, _output, registry, _job = self.layout(root)
            visible = dataset_root / "alpha-staging"
            real = dataset_root / "real"
            visible.rename(real)
            try:
                os.symlink(real, visible, target_is_directory=True)
            except OSError as exc:
                self.skipTest(str(exc))
            with self.assertRaises(dispatch.DispatchError):
                dispatch.resolve_dataset(registry, dataset_root, "alpha-staging")

    def test_dispatch_writes_only_generated_job_state(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            dataset_root, output_root, registry, job = self.layout(root)
            source = dataset_root / "alpha-staging"
            before = (source / "one.txt").read_bytes()
            with mock.patch.object(dispatch.alpha, "extract_metadata", return_value=({}, [])):
                status = dispatch.dispatch(job, registry, dataset_root, output_root)
            self.assertEqual(status["state"], "completed")
            self.assertEqual((source / "one.txt").read_bytes(), before)
            self.assertTrue((output_root / "alpha-staging" / "job-status.json").is_file())
            self.assertTrue((output_root / "alpha-staging" / "status.json").is_file())

    def test_repeat_dispatch_reuses_knowledge_records(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            dataset_root, output_root, registry, job = self.layout(root)
            with mock.patch.object(dispatch.alpha, "extract_metadata", return_value=({}, [])):
                dispatch.dispatch(job, registry, dataset_root, output_root)
                second = dispatch.dispatch(job, registry, dataset_root, output_root)
            self.assertEqual(second["state"], "completed")
            status = json.loads((output_root / "alpha-staging" / "status.json").read_text(encoding="utf-8"))
            self.assertEqual(status["summary"]["new_knowledge_records"], 0)
            self.assertEqual(status["summary"]["reused_knowledge_records"], 1)

    def test_partial_pipeline_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            dataset_root, output_root, registry, _job = self.layout(root)
            partial = contract.make_request("alpha-staging", "tester", requested_stages=["ingest"])
            with self.assertRaises(dispatch.DispatchError):
                dispatch.dispatch(partial, registry, dataset_root, output_root)

    def test_output_root_inside_dataset_root_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            dataset_root, _output, _registry, _job = self.layout(root)
            with self.assertRaises(dispatch.DispatchError):
                dispatch.output_for(dataset_root / "generated", dataset_root, "alpha-staging")

    def test_registry_rejects_path_or_credential_fields(self):
        for forbidden in ("path", "credential"):
            registry = {
                "schema": dispatch.REGISTRY_SCHEMA,
                "datasets": {
                    "alpha-staging": {
                        "enabled": True,
                        "non_production": True,
                        "read_only": True,
                        forbidden: "forbidden",
                    }
                },
            }
            with self.assertRaises(dispatch.DispatchError):
                dispatch.validate_registry(registry)

    def test_failure_records_error_type_without_exception_text(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            dataset_root, output_root, registry, job = self.layout(root)
            with mock.patch.object(dispatch.alpha, "build_snapshot", side_effect=RuntimeError("sensitive detail")):
                with self.assertRaises(RuntimeError):
                    dispatch.dispatch(job, registry, dataset_root, output_root)
            state = json.loads((output_root / "alpha-staging" / "job-status.json").read_text(encoding="utf-8"))
            self.assertEqual(state["state"], "failed")
            self.assertEqual(state["error_type"], "RuntimeError")
            self.assertNotIn("sensitive detail", json.dumps(state))


if __name__ == "__main__":
    unittest.main()
