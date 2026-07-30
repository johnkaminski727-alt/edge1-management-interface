#!/usr/bin/env python3
"""Functional and static safety tests for minimized public-summary staging."""

from __future__ import annotations

import datetime as dt
import hashlib
import importlib.util
import json
import os
import pathlib
import shutil
import stat
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVER_ROOT = ROOT / "server"
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))
MODULE_PATH = SERVER_ROOT / "edge1_public_summary_stager.py"
POLICY_PATH = ROOT / "config" / "security" / "edge1-public-summary-staging-policy.json"
SCHEMA_PATH = ROOT / "schemas" / "wwcx-edge1-public-summary-staging-policy-v1.schema.json"
STATIC_ROOT = ROOT / "src" / "web" / "public-status"
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "edge1_public_status"
SERVICE_PATH = ROOT / "deploy" / "systemd" / "wwcx-edge1-public-summary-stager.service"
TIMER_PATH = ROOT / "deploy" / "systemd" / "wwcx-edge1-public-summary-stager.timer"
APACHE_PATH = ROOT / "deploy" / "apache" / "edge1-public-summary.conf.proposed"

SPEC = importlib.util.spec_from_file_location("edge1_public_summary_stager", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def file_sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Edge1PublicSummaryStagerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.source = MODULE_PATH.read_text(encoding="utf-8")
        cls.service = SERVICE_PATH.read_text(encoding="utf-8")
        cls.timer = TIMER_PATH.read_text(encoding="utf-8")
        cls.apache = APACHE_PATH.read_text(encoding="utf-8")
        cls.now = dt.datetime(2026, 7, 30, 20, 30, tzinfo=dt.timezone.utc)

    def make_inputs(self, root: pathlib.Path) -> dict[str, pathlib.Path]:
        mapping = {
            "security": "security-operations-hostile.json",
            "network_defense": "network-defense-hostile.json",
            "operations": "operations-health-hostile.json",
        }
        paths = {}
        for key, name in mapping.items():
            target = root / f"{key}.json"
            shutil.copyfile(FIXTURE_ROOT / name, target)
            paths[key] = target
        return paths

    def make_static(self, root: pathlib.Path) -> pathlib.Path:
        target = root / "static"
        target.mkdir()
        for name in MODULE.STATIC_ASSETS:
            shutil.copyfile(STATIC_ROOT / name, target / name)
        return target

    def make_policy(
        self,
        root: pathlib.Path,
        *,
        enabled: bool,
        source_paths: dict[str, pathlib.Path],
        static_root: pathlib.Path,
        staging_root: pathlib.Path,
    ) -> pathlib.Path:
        value = json.loads(json.dumps(self.policy))
        value["enabled"] = enabled
        value["deployment_authorized"] = enabled
        value["source_paths"] = {key: str(path) for key, path in source_paths.items()}
        value["static_source_root"] = str(static_root)
        value["staging_root"] = str(staging_root)
        path = root / "policy.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def test_committed_policy_is_disabled_and_production_paths_are_exact(self) -> None:
        MODULE.validate_policy(self.policy)
        self.assertIs(self.policy["enabled"], False)
        self.assertIs(self.policy["deployment_authorized"], False)
        self.assertIs(self.policy["live_publication_authorized"], False)
        self.assertFalse(MODULE.activation_allowed(self.policy))
        self.assertEqual(
            self.schema["properties"]["contract"]["const"],
            self.policy["contract"],
        )
        self.assertEqual(
            pathlib.Path(self.policy["staging_root"]),
            MODULE.APPROVED_STAGING_ROOT,
        )
        self.assertEqual(
            {key: pathlib.Path(value) for key, value in self.policy["source_paths"].items()},
            MODULE.APPROVED_SOURCES,
        )

    def test_policy_rejects_route_header_or_publication_drift(self) -> None:
        for mutator in (
            lambda value: value["public_routes"].update(feed="/edge1-status/status.json"),
            lambda value: value["headers"].update(content_security_policy="default-src *"),
            lambda value: value.update(live_publication_authorized=True),
            lambda value: value["runtime"].update(network_access=True),
        ):
            value = json.loads(json.dumps(self.policy))
            mutator(value)
            with self.assertRaises(ValueError):
                MODULE.validate_policy(value, enforce_production_paths=False)

    def test_disabled_policy_performs_no_filesystem_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            inputs = self.make_inputs(root)
            static_root = self.make_static(root)
            staging_root = root / "staging"
            policy_path = self.make_policy(
                root,
                enabled=False,
                source_paths=inputs,
                static_root=static_root,
                staging_root=staging_root,
            )
            result = MODULE.run_from_policy(
                policy_path,
                enforce_production_paths=False,
                now=self.now,
            )
            self.assertEqual(result["state"], "disabled")
            self.assertIs(result["changed"], False)
            self.assertFalse(staging_root.exists())

    def test_stages_exact_atomic_release_with_private_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            inputs = self.make_inputs(root)
            static_root = self.make_static(root)
            staging_root = root / "staging"
            policy_path = self.make_policy(
                root,
                enabled=True,
                source_paths=inputs,
                static_root=static_root,
                staging_root=staging_root,
            )
            result = MODULE.run_from_policy(
                policy_path,
                enforce_production_paths=False,
                now=self.now,
            )
            self.assertEqual(result["state"], "staged")
            self.assertIs(result["live_publication_authorized"], False)
            self.assertIs(result["traffic_controls_changed"], False)

            current = staging_root / "current"
            self.assertTrue(current.is_symlink())
            release_root = current.resolve(strict=True)
            files = sorted(
                path.relative_to(release_root).as_posix()
                for path in release_root.rglob("*")
                if path.is_file()
            )
            self.assertEqual(files, sorted(MODULE.RELEASE_ASSETS))
            for relative in files:
                path = release_root / relative
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o644)

            status = json.loads((release_root / "public" / "status.json").read_text(encoding="utf-8"))
            self.assertEqual(status["schema_version"], "wwcx.edge1-public-status.v1")
            self.assertIs(status["read_only"], True)
            self.assertIs(status["traffic_controls_changed"], False)
            encoded = json.dumps(status, sort_keys=True)
            for forbidden in (
                "edge1-secret-host",
                "HOSTILE INTERNAL SIGNATURE",
                "10.10.10.10",
                "deadbee",
                "INC-SECRET",
                "operations-report-secret.pdf",
            ):
                self.assertNotIn(forbidden, encoded)

            metadata_root = staging_root / "metadata"
            self.assertEqual(stat.S_IMODE(metadata_root.stat().st_mode), 0o700)
            metadata_path = pathlib.Path(result["metadata"])
            self.assertEqual(stat.S_IMODE(metadata_path.stat().st_mode), 0o600)
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            self.assertEqual(metadata["release_id"], result["release_id"])
            self.assertIs(metadata["live_publication_authorized"], False)
            self.assertEqual(set(metadata["files"]), set(MODULE.RELEASE_ASSETS))
            for relative, record in metadata["files"].items():
                self.assertEqual(record["sha256"], file_sha256(release_root / relative))
                self.assertEqual(record["mode"], "0644")

    def test_existing_release_is_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            inputs = self.make_inputs(root)
            static_root = self.make_static(root)
            staging_root = root / "staging"
            MODULE.build_release(
                static_root=static_root,
                source_paths=inputs,
                staging_root=staging_root,
                now=self.now,
            )
            current_target = os.readlink(staging_root / "current")
            with self.assertRaises(FileExistsError):
                MODULE.build_release(
                    static_root=static_root,
                    source_paths=inputs,
                    staging_root=staging_root,
                    now=self.now,
                )
            self.assertEqual(os.readlink(staging_root / "current"), current_target)

    def test_tampered_or_symlinked_static_asset_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            inputs = self.make_inputs(root)
            static_root = self.make_static(root)
            staging_root = root / "staging"
            page = static_root / "index.html"
            page.write_text(page.read_text(encoding="utf-8") + "<style>bad</style>", encoding="utf-8")
            with self.assertRaises(ValueError):
                MODULE.build_release(
                    static_root=static_root,
                    source_paths=inputs,
                    staging_root=staging_root,
                    now=self.now,
                )
            self.assertFalse(staging_root.exists())

        if hasattr(os, "symlink"):
            with tempfile.TemporaryDirectory() as tmp:
                root = pathlib.Path(tmp)
                inputs = self.make_inputs(root)
                static_root = self.make_static(root)
                staging_root = root / "staging"
                app = static_root / "app.js"
                replacement = root / "replacement.js"
                replacement.write_text(app.read_text(encoding="utf-8"), encoding="utf-8")
                app.unlink()
                app.symlink_to(replacement)
                with self.assertRaises(ValueError):
                    MODULE.build_release(
                        static_root=static_root,
                        source_paths=inputs,
                        staging_root=staging_root,
                        now=self.now,
                    )

    def test_runtime_has_no_command_network_or_live_publication_operation(self) -> None:
        for token in (
            "subprocess",
            "socket",
            "requests",
            "urllib.request",
            "os.system",
            "Popen(",
            "systemctl",
            "apachectl",
            "http.server",
        ):
            self.assertNotIn(token, self.source)
        self.assertIn('APPROVED_STAGING_ROOT = Path("/var/lib/wwcx-public-summary")', self.source)
        self.assertIn('"public_tree_write",', self.source)
        self.assertNotIn("--staging-root", self.source)
        self.assertNotIn("--source", self.source)

    def test_systemd_units_are_hardened_and_not_installed(self) -> None:
        for required in (
            "Type=oneshot",
            "User=root",
            "UMask=0022",
            "NoNewPrivileges=yes",
            "ProtectSystem=strict",
            "ProtectHome=yes",
            "RestrictAddressFamilies=AF_UNIX",
            "CapabilityBoundingSet=",
            "AmbientCapabilities=",
            "ReadWritePaths=/var/lib/wwcx-public-summary",
        ):
            self.assertIn(required, self.service)
        self.assertNotIn("ReadWritePaths=/var/www", self.service)
        self.assertIn("OnUnitActiveSec=60s", self.timer)
        self.assertIn("Persistent=false", self.timer)
        self.assertFalse((ROOT / "deploy" / "install-edge1-public-summary.sh").exists())

    def test_proposed_apache_boundary_is_strict_and_non_active(self) -> None:
        self.assertTrue(self.apache.startswith("# PROPOSED ONLY"))
        self.assertIn('Alias "/edge1-status/" "/var/lib/wwcx-public-summary/current/"', self.apache)
        self.assertIn("Options -Indexes +FollowSymLinks", self.apache)
        self.assertIn("AllowOverride None", self.apache)
        self.assertIn('Header always set Cache-Control "no-store, max-age=0"', self.apache)
        self.assertIn(f'Header always set Content-Security-Policy "{MODULE.CSP}"', self.apache)
        self.assertIn('Header always set Referrer-Policy "no-referrer"', self.apache)
        self.assertIn('Header always set X-Content-Type-Options "nosniff"', self.apache)
        self.assertIn("Header always unset Access-Control-Allow-Origin", self.apache)
        self.assertNotIn("ProxyPass", self.apache)
        self.assertNotIn("AuthType", self.apache)
        self.assertEqual(APACHE_PATH.suffix, ".proposed")


if __name__ == "__main__":
    unittest.main()
