#!/usr/bin/env python3
"""Tests for the bounded read-only Edge1 live-boundary inventory collector."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import pathlib
import stat
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "server" / "edge1_live_boundary_inventory.py"
POLICY_PATH = ROOT / "config" / "security" / "edge1-live-boundary-inventory-policy.json"

SPEC = importlib.util.spec_from_file_location("edge1_live_boundary_inventory", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class Edge1LiveBoundaryInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        cls.source = MODULE_PATH.read_text(encoding="utf-8")

    def test_committed_policy_is_disabled_stdout_only_and_non_mutating(self) -> None:
        MODULE.validate_policy(self.policy)
        self.assertEqual(self.policy["contract"], MODULE.CONTRACT)
        self.assertEqual(self.policy["status"], "design_only")
        self.assertIs(self.policy["enabled"], False)
        self.assertIs(self.policy["execution_authorized"], False)
        self.assertIs(self.policy["acceptance"]["live_execution_authorized"], False)
        self.assertIs(self.policy["acceptance"]["mutation_performed"], False)
        self.assertIs(self.policy["acceptance"]["traffic_controls_changed"], False)
        self.assertIs(self.policy["output"]["stdout_only"], True)
        self.assertIs(self.policy["output"]["secret_contents"], False)
        self.assertIs(self.policy["route_probe"]["capture_body"], False)
        self.assertIs(self.policy["route_probe"]["capture_set_cookie_values"], False)
        self.assertIs(self.policy["route_probe"]["capture_location_query"], False)

        status = MODULE.design_status(self.policy)
        self.assertIs(status["enabled"], False)
        self.assertIs(status["execution_authorized"], False)
        self.assertIs(status["live_execution_authorized"], False)
        self.assertIs(status["mutation_performed"], False)

    def test_policy_rejects_partial_authorization_and_weakened_boundaries(self) -> None:
        mutations = (
            lambda value: value.update(enabled=True),
            lambda value: value.update(repository_root="/tmp/repository"),
            lambda value: value["filesystem_roots"].append("/etc"),
            lambda value: value["metadata_only_paths"].append("/etc/shadow"),
            lambda value: value["route_paths"].append("/edge1-ops/?token=secret"),
            lambda value: value["command_candidates"]["curl"].append("/tmp/curl"),
            lambda value: value["route_probe"].update(capture_body=True),
            lambda value: value["route_probe"].update(maximum_redirects=5),
            lambda value: value["output"].update(raw_cookie_values=True),
            lambda value: value["output"].update(raw_location_queries=True),
            lambda value: value["acceptance"].update(filesystem_follow_symlinks=True),
            lambda value: value["acceptance"].update(mutation_performed=True),
            lambda value: value["acceptance"].update(traffic_controls_changed=True),
        )
        for mutate in mutations:
            value = copy.deepcopy(self.policy)
            mutate(value)
            with self.subTest(mutate=mutate):
                with self.assertRaises(ValueError):
                    MODULE.validate_policy(value)

    def test_policy_accepts_only_complete_execution_authorization(self) -> None:
        value = copy.deepcopy(self.policy)
        value["enabled"] = True
        value["execution_authorized"] = True
        value["acceptance"]["live_execution_authorized"] = True
        MODULE.validate_policy(value)

    def test_tree_inventory_hashes_regular_files_and_never_follows_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "root"
            root.mkdir()
            data = b"edge1-boundary-evidence\n"
            regular = root / "status.json"
            regular.write_bytes(data)
            nested = root / "reports"
            nested.mkdir()
            (nested / "index.json").write_text("{}\n", encoding="utf-8")
            outside = pathlib.Path(tmp) / "outside-secret"
            outside.write_text("must-not-be-read", encoding="utf-8")
            symlink_supported = hasattr(os, "symlink")
            if symlink_supported:
                (root / "outside-link").symlink_to(outside)

            result = MODULE.inventory_tree(root, self.policy["limits"])
            self.assertIs(result["complete"], True)
            records = {item["relative_path"]: item for item in result["entries"]}
            self.assertEqual(
                records["status.json"]["sha256"],
                hashlib.sha256(data).hexdigest(),
            )
            self.assertEqual(records["status.json"]["hash_state"], "hashed")
            self.assertEqual(records["reports"]["type"], "directory")
            if symlink_supported:
                self.assertEqual(records["outside-link"]["type"], "symlink")
                self.assertNotIn("sha256", records["outside-link"])
                self.assertEqual(result["counts"]["symlinks"], 1)
            self.assertEqual(result["counts"]["regular_files"], 2)

    def test_tree_inventory_reports_file_and_total_limits_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "large.bin").write_bytes(b"a" * 16)
            limits = dict(self.policy["limits"])
            limits["maximum_single_file_bytes"] = 8
            result = MODULE.inventory_tree(root, limits)
            record = result["entries"][0]
            self.assertIs(record["sha256"], None)
            self.assertEqual(record["hash_state"], "single_file_limit")
            self.assertIs(result["complete"], False)
            self.assertEqual((root / "large.bin").read_bytes(), b"a" * 16)

            limits = dict(self.policy["limits"])
            limits["maximum_total_file_bytes"] = 8
            result = MODULE.inventory_tree(root, limits)
            record = result["entries"][0]
            self.assertIs(record["sha256"], None)
            self.assertEqual(record["hash_state"], "total_file_limit")
            self.assertIs(result["complete"], False)

    def test_metadata_only_paths_do_not_hash_or_disclose_symlink_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            secret = root / "client-secret"
            secret.write_text("do-not-disclose", encoding="utf-8")
            records = MODULE.inventory_metadata_only([str(secret)])
            self.assertEqual(records[0]["type"], "regular")
            self.assertNotIn("sha256", records[0])
            self.assertNotIn("do-not-disclose", json.dumps(records))

            if hasattr(os, "symlink"):
                link = root / "secret-link"
                link.symlink_to(secret)
                record = MODULE.inventory_metadata_only([str(link)])[0]
                self.assertEqual(record["type"], "symlink")
                self.assertEqual(record["symlink_target"], "redacted")
                self.assertNotIn(str(secret), json.dumps(record))

    def test_apache_inventory_allowlists_directives_and_omits_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            config = root / "sites-enabled" / "edge1.conf"
            config.parent.mkdir()
            config.write_text(
                "\n".join((
                    "# comment",
                    'Alias /edge1-status/ /var/www/edge1-status/',
                    'Header always set Cache-Control "no-store"',
                    "OIDCClientID public-client-id",
                    "OIDCClientSecret super-secret-value",
                    "OIDCCryptoPassphrase another-secret-value",
                    "SSLCertificateKeyFile /etc/ssl/private/key.pem",
                    "Require valid-user",
                )) + "\n",
                encoding="utf-8",
            )
            policy = copy.deepcopy(self.policy)
            policy["apache_config_root"] = str(root)
            result = MODULE.apache_config_inventory(policy)
            directives = result["directives"]
            names = [item["directive"] for item in directives]
            self.assertIn("Alias", names)
            self.assertIn("Header", names)
            self.assertIn("OIDCClientID", names)
            self.assertIn("Require", names)
            encoded = json.dumps(result, sort_keys=True)
            self.assertNotIn("super-secret-value", encoded)
            self.assertNotIn("another-secret-value", encoded)
            self.assertNotIn("/etc/ssl/private/key.pem", encoded)

    def test_route_header_parser_redacts_cookie_values_and_location_queries(self) -> None:
        headers = (
            "HTTP/1.1 302 Found\r\n"
            "Cache-Control: no-store\r\n"
            "Content-Security-Policy: default-src 'self'\r\n"
            "Location: https://idp.example/authorize?client_id=abc&state=secret-state\r\n"
            "Set-Cookie: __Secure-session=secret-cookie-value; Path=/edge1-ops/; Secure; HttpOnly; SameSite=Strict\r\n"
            "WWW-Authenticate: Bearer realm=restricted\r\n"
            "\r\n"
        )
        result = MODULE.parse_header_output(headers)
        self.assertIs(result["parsed"], True)
        self.assertEqual(result["status"], 302)
        self.assertEqual(result["location"]["path"], "/authorize")
        self.assertIs(result["location"]["query_present"], True)
        self.assertIs(result["location"]["query_captured"], False)
        self.assertEqual(result["www_authenticate_schemes"], ["Bearer"])
        cookie = result["cookies"][0]
        self.assertEqual(cookie["name"], "__Secure-session")
        self.assertIs(cookie["secure"], True)
        self.assertIs(cookie["http_only"], True)
        self.assertEqual(cookie["same_site"], "Strict")
        self.assertIs(cookie["value_captured"], False)
        encoded = json.dumps(result, sort_keys=True)
        self.assertNotIn("secret-cookie-value", encoded)
        self.assertNotIn("secret-state", encoded)
        self.assertNotIn("client_id=abc", encoded)

    def test_route_probe_uses_head_without_redirects_or_body(self) -> None:
        response = {
            "available": True,
            "stdout": "HTTP/1.1 200 OK\r\nCache-Control: no-store\r\n\r\n",
            "stderr": "",
            "returncode": 0,
        }
        with mock.patch.object(MODULE, "command_result", return_value=response) as called:
            result = MODULE.route_probe(self.policy, "/edge1-status/", local=True)
        key, arguments = called.call_args.args
        self.assertEqual(key, "curl")
        self.assertIn("--head", arguments)
        self.assertIn("--max-redirs", arguments)
        self.assertIn("0", arguments)
        self.assertIn("--resolve", arguments)
        self.assertNotIn("--location", arguments)
        self.assertIs(result["body_captured"], False)
        self.assertIs(result["raw_cookie_values_captured"], False)
        self.assertEqual(result["response"]["status"], 200)

    def test_command_resolution_and_runner_are_bounded(self) -> None:
        with self.assertRaises(KeyError):
            MODULE.resolve_command(self.policy, "shell")
        text, truncated = MODULE.bounded_text(b"abcdef", 3)
        self.assertEqual(text, "abc")
        self.assertIs(truncated, True)
        with self.assertRaises(ValueError):
            MODULE.run_command(
                ["relative-command"],
                timeout_seconds=1,
                maximum_output_bytes=100,
            )

    def test_source_has_no_host_mutation_or_output_file_interface(self) -> None:
        forbidden = (
            "os.remove(",
            "os.unlink(",
            ".unlink(",
            ".rename(",
            ".replace(",
            ".write_text(",
            ".write_bytes(",
            "open(\"w",
            "open('w",
            "chmod(",
            "chown(",
            "mkdir(",
            "makedirs(",
            '"start"',
            '"restart"',
            '"reload"',
            '"enable"',
            '"disable"',
            "a2enmod",
            "a2ensite",
            "a2enconf",
            "iptables",
            "nft ",
            "firewall-cmd",
            "--output",
        )
        for token in forbidden:
            self.assertNotIn(token, self.source)
        self.assertIn("writes only JSON to stdout", self.source)
        self.assertIn("--ack-read-only", self.source)
        self.assertIn("live inventory is not authorized by policy", self.source)
        self.assertIn('"mutation_performed": False', self.source)
        self.assertIn('"traffic_controls_changed": False', self.source)


if __name__ == "__main__":
    unittest.main()
