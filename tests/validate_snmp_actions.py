#!/usr/bin/env python3
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

from edge1_snmp_actions import execute_proposal
from edge1_snmp_platform import add_device, connect_db, propose_action
from edge1_snmp_services import ensure_extended_schema


class ActionExecutorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = connect_db(Path(self.tmp.name) / "snmp.db")
        ensure_extended_schema(self.conn)
        self.device = add_device(self.conn, {
            "display_name": "router-01",
            "management_address": "10.20.30.1",
            "credential_reference": "router-v3",
        })

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def proposal(self, action, *, target=None, validation=None, rollback=None):
        return propose_action(
            self.conn,
            actor="ai-operator",
            action=action,
            target=target,
            reason="test remediation",
            ai_involvement=True,
            validation=validation,
            rollback=rollback,
        )

    def test_unapproved_proposal_cannot_execute(self):
        proposal = self.proposal("disable_broken_polling", target=self.device["device_id"])
        self.assertEqual(proposal["state"], "pending_review")
        with self.assertRaises(PermissionError):
            execute_proposal(self.conn, proposal["proposal_id"])

    def test_disable_polling_executes_and_audits(self):
        proposal = self.proposal(
            "disable_broken_polling",
            target=self.device["device_id"],
            validation={"reason": "repeated malformed responses"},
            rollback={"polling_enabled": True},
        )
        result = execute_proposal(self.conn, proposal["proposal_id"])
        self.assertEqual(result["state"], "executed")
        enabled = self.conn.execute("SELECT polling_enabled FROM devices WHERE device_id=?", (self.device["device_id"],)).fetchone()[0]
        self.assertEqual(enabled, 0)
        audit_count = self.conn.execute("SELECT count(*) FROM audit WHERE action='action.execute.disable_broken_polling'").fetchone()[0]
        self.assertEqual(audit_count, 1)

    def test_poll_interval_is_bounded(self):
        proposal = self.proposal(
            "temporarily_adjust_polling",
            target=self.device["device_id"],
            validation={"new_interval_seconds": 5},
            rollback={"polling_interval": 300},
        )
        with self.assertRaises(ValueError):
            execute_proposal(self.conn, proposal["proposal_id"])
        state = self.conn.execute("SELECT state FROM action_proposals WHERE proposal_id=?", (proposal["proposal_id"],)).fetchone()[0]
        self.assertEqual(state, "failed")

    def test_restart_is_fixed_allowlist_only(self):
        bad = self.proposal(
            "restart_snmp_service",
            target="ssh.service",
            validation={"health_check": "/api/snmp/health"},
            rollback={"action": "restart_previous"},
        )
        with self.assertRaises(PermissionError):
            execute_proposal(self.conn, bad["proposal_id"])

        good = self.proposal(
            "restart_snmp_service",
            target="edge1-snmp-api.service",
            validation={"health_check": "/api/snmp/health"},
            rollback={"action": "restart_previous"},
        )
        captured = {}
        def runner(argv, **kwargs):
            captured["argv"] = argv
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        result = execute_proposal(self.conn, good["proposal_id"], service_runner=runner)
        self.assertEqual(result["state"], "executed")
        self.assertEqual(captured["argv"], ["/usr/bin/systemctl", "restart", "edge1-snmp-api.service"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
