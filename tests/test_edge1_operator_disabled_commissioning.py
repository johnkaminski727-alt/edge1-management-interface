#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
COMMISSION = (ROOT / "deploy/edge1-operator/commission-controls-v1-disabled.sh").read_text(encoding="utf-8")
OPERATOR_PIN = (ROOT / "deploy/pin-edge1-operator-mcp-runtime.sh").read_text(encoding="utf-8")
OPS_PIN = (ROOT / "deploy/pin-edge1-operations-api-runtime.sh").read_text(encoding="utf-8")
BROKER_INSTALL = (ROOT / "deploy/edge1-operator/install-privileged-broker-v1.sh").read_text(encoding="utf-8")
LIVE_VALIDATOR = (ROOT / "tools/operator/validate_controls_disabled_live.py").read_text(encoding="utf-8")


class DisabledCommissioningTests(unittest.TestCase):
    def test_operator_runtime_is_immutable_and_read_scoped(self):
        self.assertIn("/opt/edge1-operator-mcp-runtimes/", OPERATOR_PIN)
        self.assertIn("WorkingDirectory=$RUNTIME", OPERATOR_PIN)
        self.assertIn(
            "ExecStart=/usr/bin/env --chdir=$RUNTIME "
            "EDGE1_OPERATOR_CAPABILITIES=$RUNTIME/config/edge1-operator-capabilities.json "
            "EDGE1_OPERATOR_SCOPES=$READ_SCOPES /usr/bin/python3 -m server.edge1_operator_http",
            OPERATOR_PIN,
        )
        self.assertIn("/usr/bin/env --help", OPERATOR_PIN)
        self.assertIn("'--chdir'", OPERATOR_PIN)
        self.assertIn("cwd_enforcement=fixed_execstart_env_chdir", OPERATOR_PIN)
        scope_lines = [line for line in OPERATOR_PIN.splitlines() if line.startswith("READ_SCOPES=")]
        self.assertEqual(
            scope_lines,
            ["READ_SCOPES=edge1.status.read,edge1.telephony.read,edge1.messaging.read"],
        )
        self.assertIn('/proc/{pid}/environ', OPERATOR_PIN)
        self.assertIn('effective Operator scope set mismatch', OPERATOR_PIN)
        self.assertIn('write scope unexpectedly present', OPERATOR_PIN)
        self.assertNotIn("EDGE1_OPERATOR_SCOPES=edge1.telephony.control.safe", OPERATOR_PIN)

    def test_operator_worktree_is_readable_by_service_but_not_group_writable(self):
        self.assertIn("OPERATOR_SERVICE_USER=edge1-operator", COMMISSION)
        self.assertIn("OPERATOR_SERVICE_GROUP=edge1-operator", COMMISSION)
        self.assertIn('sudo chgrp -R "$OPERATOR_SERVICE_GROUP" "$OPERATOR_RUNTIME"', COMMISSION)
        self.assertIn('sudo chmod -R g+rX,o-rwx "$OPERATOR_RUNTIME"', COMMISSION)
        self.assertIn('sudo -u "$OPERATOR_SERVICE_USER" test -x "$OPERATOR_RUNTIME"', COMMISSION)
        self.assertIn('sudo -u "$OPERATOR_SERVICE_USER" test -r "$OPERATOR_RUNTIME/$rel"', COMMISSION)
        self.assertIn("PYTHONDONTWRITEBYTECODE=1", COMMISSION)
        self.assertNotIn('chmod -R g+w', COMMISSION)
        self.assertNotIn('chmod -R a+w', COMMISSION)

    def test_reviewed_control_base_tolerates_only_unrelated_main_drift(self):
        self.assertIn("--reviewed-control-base", COMMISSION)
        self.assertIn('git merge-base --is-ancestor "$REVIEWED_CONTROL_BASE" "$REMOTE"', COMMISSION)
        self.assertIn('CONTROL_DIFF=$(git diff --name-only "$REVIEWED_CONTROL_BASE..$REMOTE" --', COMMISSION)
        for protected in (
            "deploy/edge1-operator",
            "deploy/pin-edge1-operator-mcp-runtime.sh",
            "deploy/pin-edge1-operations-api-runtime.sh",
            "config/edge1-operator-capabilities.json",
            "config/edge1-operations-allowlist.json",
            "server/edge1_operator_http.py",
            "server/edge1_operations_api.py",
            "server/edge1_operations_typed_actions.py",
            "server/asterisk_process_identity.py",
            "tools/operator",
        ):
            self.assertIn(protected, COMMISSION)
        self.assertIn('fail "fresh control-plane review is required"', COMMISSION)
        self.assertIn("resolved_deploy_commit=$DEPLOY_COMMIT", COMMISSION)
        self.assertIn("EXPECTED_COMMIT=$DEPLOY_COMMIT", COMMISSION)

    def test_failed_child_output_is_visible_and_err_trap_is_not_inherited(self):
        self.assertIn("set -euo pipefail", COMMISSION)
        self.assertNotIn("set -Eeuo pipefail", COMMISSION)
        for token in ("BROKER_LOG=$(mktemp)", "OPS_LOG=$(mktemp)", "OPERATOR_LOG=$(mktemp)"):
            self.assertIn(token, COMMISSION)
        self.assertIn('| tee "$OPERATOR_LOG"', COMMISSION)

    def test_operator_pin_captures_safe_failure_evidence(self):
        self.assertIn("capture_failure_evidence()", OPERATOR_PIN)
        self.assertIn("service.failure.txt", OPERATOR_PIN)
        self.assertIn("journal.failure.txt", OPERATOR_PIN)
        self.assertIn("failure_evidence=$EVID", OPERATOR_PIN)
        self.assertIn('process_cwd=$(readlink', OPERATOR_PIN)
        self.assertNotIn("systemctl show -p Environment --value", OPERATOR_PIN)

    def test_operations_runtime_explicitly_leaves_safe_gate_off(self):
        self.assertIn("EDGE1_OPS_TELEPHONY_SAFE_CONTROLS_ENABLED=false", OPS_PIN)
        self.assertIn('data.get("mutations_enabled") is not False', OPS_PIN)
        self.assertIn('get("telephony_safe_controls") is not False', OPS_PIN)
        self.assertNotIn("EDGE1_OPS_TELEPHONY_SAFE_CONTROLS_ENABLED=true", OPS_PIN)

    def test_commissioning_never_creates_approval_or_enables_write(self):
        self.assertIn("APPROVAL_MARKER=/etc/wwcx-edge1-operator/telephony-console-control.json", COMMISSION)
        self.assertIn('sudo test ! -e "$APPROVAL_MARKER"', COMMISSION)
        self.assertNotIn("telephony-console-control.json <<", COMMISSION)
        self.assertNotIn("EDGE1_OPS_TELEPHONY_SAFE_CONTROLS_ENABLED=true", COMMISSION)
        self.assertNotIn("edge1.telephony.control.safe", COMMISSION)
        self.assertIn("calls_or_messages_generated=false", COMMISSION)

    def test_protected_service_pids_must_not_change(self):
        for token in (
            "Asterisk PID changed during disabled commissioning",
            "Messaging Gateway PID changed during disabled commissioning",
            "Telephony Console PID changed during disabled commissioning",
            "Secure MCP Tunnel PID changed during disabled commissioning",
        ):
            self.assertIn(token, COMMISSION)
        self.assertNotIn("systemctl restart wwcx-telephony-console.service", COMMISSION)
        self.assertNotIn("systemctl restart asterisk.service", COMMISSION)
        self.assertNotIn("systemctl restart wwcx-messaging-gateway.service", COMMISSION)

    def test_broker_release_packages_fixed_asterisk_identity_helper(self):
        self.assertIn("HELPER_REL=server/asterisk_process_identity.py", BROKER_INSTALL)
        self.assertIn('"$RELEASE/asterisk_process_identity.py"', BROKER_INSTALL)
        self.assertIn("existing immutable helper hash mismatch", BROKER_INSTALL)

    def test_live_acceptance_proves_write_denied_before_broker(self):
        self.assertIn('"edge1.telephony_console_reload"', LIVE_VALIDATOR)
        self.assertIn('{"message": "capability_denied"}', LIVE_VALIDATOR)
        self.assertIn("privileged_broker_not_reached_by_denied_write", LIVE_VALIDATOR)
        self.assertIn("authorized_attempt", LIVE_VALIDATOR)


if __name__ == "__main__":
    unittest.main()
