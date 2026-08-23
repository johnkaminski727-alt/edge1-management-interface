#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from server import asterisk_process_identity as identity


class AsteriskProcessIdentityTests(unittest.TestCase):
    def test_prefers_valid_systemd_mainpid(self):
        with mock.patch.object(identity, "_run", return_value=SimpleNamespace(returncode=0, stdout="123\n")), \
             mock.patch.object(identity, "_valid_pid", side_effect=lambda value: 123 if str(value).strip() == "123" else None):
            self.assertEqual(identity.resolve_asterisk_pid(), (123, "systemd:MainPID"))

    def test_uses_pidfile_when_sysv_unit_has_mainpid_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            pidfile = Path(tmp) / "asterisk.pid"
            pidfile.write_text("456\n", encoding="utf-8")
            with mock.patch.object(identity, "PIDFILES", (pidfile,)), \
                 mock.patch.object(identity, "_run", return_value=SimpleNamespace(returncode=0, stdout="0\n")), \
                 mock.patch.object(identity, "_valid_pid", side_effect=lambda value: 456 if str(value).strip() == "456" else None):
                self.assertEqual(identity.resolve_asterisk_pid(), (456, f"pidfile:{pidfile}"))

    def test_valid_pid_rejects_zero_and_non_numeric(self):
        self.assertIsNone(identity._valid_pid(0))
        self.assertIsNone(identity._valid_pid("nope"))


if __name__ == "__main__":
    unittest.main()
