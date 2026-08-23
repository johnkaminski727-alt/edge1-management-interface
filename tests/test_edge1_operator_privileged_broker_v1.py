#!/usr/bin/env python3
from __future__ import annotations

import json
import pathlib
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

from server import edge1_operator_privileged_broker as broker
from server import edge1_operations_typed_actions as typed

ROOT = pathlib.Path(__file__).resolve().parents[1]
UNIT = (ROOT / "deploy/edge1-operator/edge1-operator-privileged-broker.service").read_text(encoding="utf-8")
INSTALLER = (ROOT / "deploy/edge1-operator/install-privileged-broker-v1.sh").read_text(encoding="utf-8")
BROKER_SOURCE = (ROOT / "server/edge1_operator_privileged_broker.py").read_text(encoding="utf-8")
TYPED_SOURCE = (ROOT / "server/edge1_operations_typed_actions.py").read_text(encoding="utf-8")


def valid_request() -> dict[str, object]:
    return {
        "version": 1,
        "action": "telephony_console_reload",
        "request_id": "broker-request-0001",
        "expected_pid": 123,
        "expected_source_sha256": "a" * 64,
        "expected_repo_head": "b" * 40,
    }


class PrivilegedBrokerV1Tests(unittest.TestCase):
    def test_protocol_accepts_only_fixed_action_and_fields(self):
        value = broker._validate_request(valid_request())
        self.assertEqual(value["action"], "telephony_console_reload")
        for field in ("service", "command", "argv", "path", "url", "host", "port", "environment", "sql"):
            bad = valid_request()
            bad[field] = "forbidden"
            with self.subTest(field=field), self.assertRaises(broker.BrokerRequestError):
                broker._validate_request(bad)
        bad_action = valid_request()
        bad_action["action"] = "asterisk_restart"
        with self.assertRaises(broker.BrokerRequestError):
            broker._validate_request(bad_action)

    def test_peer_requires_expected_uid_and_operations_api_cgroup(self):
        fake_user = SimpleNamespace(pw_uid=1000, pw_gid=1000)
        with mock.patch.object(broker.pwd, "getpwnam", return_value=fake_user):
            with mock.patch.object(pathlib.Path, "read_text", return_value="0::/system.slice/edge1-operations-api.service\n"):
                self.assertTrue(broker._peer_is_operations_api(222, 1000))
                self.assertFalse(broker._peer_is_operations_api(222, 0))
            with mock.patch.object(pathlib.Path, "read_text", return_value="0::/user.slice/user-1000.slice/session.scope\n"):
                self.assertFalse(broker._peer_is_operations_api(222, 1000))

    def test_source_must_be_tracked_and_clean_at_head(self):
        with mock.patch.object(broker, "_run") as run:
            run.side_effect = [
                SimpleNamespace(returncode=0),
                SimpleNamespace(returncode=0),
            ]
            self.assertTrue(broker._source_matches_head())
        with mock.patch.object(broker, "_run") as run:
            run.side_effect = [
                SimpleNamespace(returncode=0),
                SimpleNamespace(returncode=1),
            ]
            self.assertFalse(broker._source_matches_head())

    def test_execute_refuses_dirty_source_before_systemctl_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = pathlib.Path(tmp) / "telephony.py"
            source.write_text("print('reviewed')\n", encoding="utf-8")
            with mock.patch.object(broker, "SOURCE", source), \
                 mock.patch.object(broker, "_source_matches_head", return_value=False), \
                 mock.patch.object(broker, "_run") as run:
                with self.assertRaises(RuntimeError, msg="dirty source must fail closed"):
                    broker._execute_reload(valid_request())
                run.assert_not_called()

    def test_unit_is_unix_only_root_broker_with_no_capabilities(self):
        self.assertIn("User=root\n", UNIT)
        self.assertIn("Group=wwadmin\n", UNIT)
        self.assertIn("NoNewPrivileges=true\n", UNIT)
        self.assertIn("RestrictAddressFamilies=AF_UNIX\n", UNIT)
        self.assertIn("CapabilityBoundingSet=\n", UNIT)
        self.assertIn("AmbientCapabilities=\n", UNIT)
        self.assertIn("ProtectSystem=strict\n", UNIT)
        self.assertIn("PrivateDevices=true\n", UNIT)
        self.assertIn(
            "ExecStart=/usr/bin/python3 /usr/local/libexec/edge1-operator-privileged-broker/current/edge1_operator_privileged_broker.py\n",
            UNIT,
        )
        self.assertNotIn("ExecStart=/bin/sh", UNIT)
        self.assertNotIn("/opt/edge1-management-interface/server/edge1_operator_privileged_broker.py", UNIT)

    def test_broker_contains_only_fixed_systemctl_restart_target(self):
        self.assertIn('["systemctl", "restart", TELEPHONY_SERVICE]', BROKER_SOURCE)
        self.assertNotIn("shell=True", BROKER_SOURCE)
        self.assertNotIn("edge1_agent_exec", BROKER_SOURCE)
        self.assertNotIn("/bin/sh", BROKER_SOURCE)
        self.assertNotIn("sudo", BROKER_SOURCE)
        self.assertEqual(BROKER_SOURCE.count('["systemctl", "restart",'), 1)

    def test_unprivileged_typed_handler_has_no_direct_systemctl_restart(self):
        self.assertIn('BROKER_SOCKET = "/run/edge1-operator-privileged/control.sock"', TYPED_SOURCE)
        self.assertIn("socket.AF_UNIX", TYPED_SOURCE)
        self.assertNotIn('["systemctl", "restart", SERVICE]', TYPED_SOURCE)

    def test_installer_is_dry_run_by_default_and_immutable(self):
        self.assertIn("MODE=dry-run", INSTALLER)
        self.assertIn("--apply", INSTALLER)
        self.assertIn("/usr/local/libexec/edge1-operator-privileged-broker", INSTALLER)
        self.assertIn("install -o root -g root -m 0444", INSTALLER)
        self.assertIn("non_operations_peer_denied=true", INSTALLER)
        self.assertIn("operations_safe_gate_enabled=false", INSTALLER)
        self.assertNotIn("EDGE1_OPS_TELEPHONY_SAFE_CONTROLS_ENABLED=true", INSTALLER)
        self.assertNotIn("EDGE1_OPS_MUTATIONS_ENABLED=true", INSTALLER)

    def test_root_side_audit_is_required_before_execute(self):
        class FakeConn:
            def __init__(self):
                self.sent = []
            def sendall(self, data):
                self.sent.append(data)

        conn = FakeConn()
        events: list[str] = []
        with mock.patch.object(broker, "_peer_credentials", return_value=(222, 1000, 1000)), \
             mock.patch.object(broker, "_peer_is_operations_api", return_value=True), \
             mock.patch.object(broker, "_receive_request", return_value=valid_request()), \
             mock.patch.object(broker, "_audit", side_effect=lambda record: events.append(record["status"])), \
             mock.patch.object(broker, "_execute_reload", return_value={
                 "version": 1,
                 "action": "telephony_console_reload",
                 "request_id": "broker-request-0001",
                 "status": "succeeded",
                 "pid_before": 123,
                 "pid_after": 124,
             }):
            broker._serve_connection(conn)
        self.assertEqual(events[:2], ["authorized_attempt", "succeeded"])
        payload = json.loads(conn.sent[-1].decode())
        self.assertEqual(payload["status"], "succeeded")


if __name__ == "__main__":
    unittest.main()
