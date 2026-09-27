#!/usr/bin/env python3
"""Offline regressions for guarded restore; every command is mocked."""
import importlib.util
import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

src = Path(__file__).resolve().parents[1] / "tools/networking/spamhaus_guarded_boot_restore.py"
spec = importlib.util.spec_from_file_location("guarded", src)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def ok(args, stdout=""):
    return subprocess.CompletedProcess(args, 0, stdout, "")

class Fake:
    def __init__(self, *, present=False, stale=False, arm_fail=False,
                 apply_fail=False, timer_fail=False, invalid_table=False):
        self.present, self.stale, self.arm_fail = present, stale, arm_fail
        self.apply_fail, self.timer_fail, self.invalid_table = apply_fail, timer_fail, invalid_table
        self.commands = []
    def __call__(self, args, *, timeout=60):
        self.commands.append(list(args))
        if args[:4] == [m.NFT, "-j", "list", "tables"]:
            names = [{"table": {"family": "inet", "name": "ufw"}}]
            if self.present:
                names.append({"table": {"family": "inet", "name": "bigbird_spamhaus"}})
            return ok(args, json.dumps({"nftables": names}))
        if args[:4] == [m.NFT, "-j", "list", "table"]:
            if self.invalid_table:
                return ok(args, json.dumps({"nftables": [{"table": {"family": "inet", "name": "bigbird_spamhaus"}}]}))
            expr = lambda fam, name: [
                {"match": {"left": {"payload": {"protocol": fam, "field": "saddr"}},
                           "op": "==", "right": "@" + name}},
                {"counter": {"packets": 0, "bytes": 0}}, {"drop": None}]
            records = [{"set": {"name": "drop4", "type": "ipv4_addr", "flags": ["interval"], "elem": ["203.0.113.0/24"]}},
                       {"set": {"name": "drop6", "type": "ipv6_addr", "flags": ["interval"], "elem": ["2001:db8::/32"]}}]
            for chain in ("input", "forward"):
                records.append({"chain": {"name": chain, "hook": chain, "type": "filter", "prio": -110, "policy": "accept"}})
                for fam, name in (("ip", "drop4"), ("ip6", "drop6")):
                    records.append({"rule": {"chain": chain, "expr": expr(fam, name)}})
            return ok(args, json.dumps({"nftables": records}))
        if args[0] == m.SYSTEMD_RUN:
            return subprocess.CompletedProcess(args, 1 if self.arm_fail else 0, "", "")
        if args[:3] == [m.SYSTEMCTL, "show", m.TIMER]:
            if "--property=Unit" in args:
                return ok(args, m.SERVICE + "\n")
            return ok(args, "inactive\n" if self.timer_fail else "active\n")
        if args[:3] == [m.SYSTEMCTL, "show", m.SERVICE]:
            return ok(args, "path=" + m.PYTHON + " ; argv[]=" + m.PYTHON + " -B " + str(m.RECOVERY) + " --execute ;")
        if args[:2] == [m.NFT, "--file"]:
            if self.apply_fail:
                return subprocess.CompletedProcess(args, 1, "", "")
            self.present = True
            return ok(args)
        if "spamhaus_boot_preflight.py" in " ".join(map(str, args)) and self.stale:
            return subprocess.CompletedProcess(args, 1, "", "stale")
        return ok(args)

class GuardedTests(unittest.TestCase):
    def invoke(self, fake, *, execute=True):
        with patch.object(m, "run", fake), patch.object(m, "validate_sources",
            side_effect=lambda: self.mock_validate(fake)):
            return m.guarded_restore(execute=execute)

    def mock_validate(self, fake):
        m.require([m.CHRONYC, "waitsync", "30", "0.1"], "Clock not synchronized")
        for unit in m.REQUIRED_SERVICES:
            m.require([m.SYSTEMCTL, "is-active", "--quiet", unit], "Service not ready")
        m.require([m.PYTHON, "-B", str(m.PREFLIGHT), "--stage", str(m.STAGE),
                   "--parser", str(m.PARSER), "--recovery", str(m.RECOVERY)], "Feed stale")
        m.require([m.NFT, "--check", "--file", str(m.CANDIDATE)], "Candidate invalid")

    def test_check_only_never_arms_or_applies(self):
        f = Fake()
        self.assertEqual(self.invoke(f, execute=False), "eligible_check_only")
        self.assertFalse(any(c[0] in (m.SYSTEMD_RUN,) or c[:2] == [m.NFT, "--file"] for c in f.commands))

    def test_success_arms_before_apply_and_leaves_timer_active(self):
        f = Fake()
        self.assertEqual(self.invoke(f), "restored_verified_rollback_armed")
        arm = next(i for i,c in enumerate(f.commands) if c[0] == m.SYSTEMD_RUN)
        apply = next(i for i,c in enumerate(f.commands) if c[:2] == [m.NFT, "--file"])
        self.assertLess(arm, apply)
        self.assertFalse(any("stop" in c for c in f.commands))

    def test_duplicate_table_never_arms_or_applies(self):
        f = Fake(present=True)
        self.assertEqual(self.invoke(f), "already_present")
        self.assertEqual(len(f.commands), 1)

    def test_expired_feed_blocks_arming(self):
        f = Fake(stale=True)
        with self.assertRaises(RuntimeError): self.invoke(f)
        self.assertFalse(any(c[0] == m.SYSTEMD_RUN for c in f.commands))

    def test_timer_arming_failure_blocks_apply(self):
        f = Fake(arm_fail=True)
        with self.assertRaises(RuntimeError): self.invoke(f)
        self.assertFalse(any(c[:2] == [m.NFT, "--file"] for c in f.commands))

    def test_timer_state_failure_blocks_apply(self):
        f = Fake(timer_fail=True)
        with self.assertRaises(RuntimeError): self.invoke(f)
        self.assertFalse(any(c[:2] == [m.NFT, "--file"] for c in f.commands))

    def test_failed_apply_leaves_rollback_armed(self):
        f = Fake(apply_fail=True)
        with self.assertRaises(RuntimeError): self.invoke(f)
        self.assertTrue(any(c[0] == m.SYSTEMD_RUN for c in f.commands))
        self.assertFalse(any("stop" in c for c in f.commands))

    def test_rejects_wrong_payload_field(self):
        f = Fake()
        old = m.verify_restored_table
        def wrong_field():
            def runner(args, *, timeout=60):
                result = f(args, timeout=timeout)
                if args[:4] == [m.NFT, "-j", "list", "table"]:
                    doc = json.loads(result.stdout)
                    rule = next(e["rule"] for e in doc["nftables"] if "rule" in e)
                    rule["expr"][0]["match"]["left"]["payload"]["field"] = "daddr"
                    return ok(args, json.dumps(doc))
                return result
            with patch.object(m, "run", runner):
                m.verify_restored_table()
        with self.assertRaises(RuntimeError):
            wrong_field()

    def test_rejects_wrong_match_operator(self):
        f = Fake()
        def runner(args, *, timeout=60):
            result = f(args, timeout=timeout)
            if args[:4] == [m.NFT, "-j", "list", "table"]:
                doc = json.loads(result.stdout)
                rule = next(e["rule"] for e in doc["nftables"] if "rule" in e)
                rule["expr"][0]["match"]["op"] = "!="
                return ok(args, json.dumps(doc))
            return result
        with patch.object(m, "run", runner):
            with self.assertRaises(RuntimeError):
                m.verify_restored_table()

    def test_rejects_missing_counter(self):
        f = Fake()
        def runner(args, *, timeout=60):
            result = f(args, timeout=timeout)
            if args[:4] == [m.NFT, "-j", "list", "table"]:
                doc = json.loads(result.stdout)
                rule = next(e["rule"] for e in doc["nftables"] if "rule" in e)
                rule["expr"].pop(1)
                return ok(args, json.dumps(doc))
            return result
        with patch.object(m, "run", runner):
            with self.assertRaises(RuntimeError):
                m.verify_restored_table()

    def test_incomplete_rules_leave_rollback_armed(self):
        f = Fake(invalid_table=True)
        with self.assertRaises(RuntimeError): self.invoke(f)
        self.assertTrue(any(c[0] == m.SYSTEMD_RUN for c in f.commands))
        self.assertFalse(any("stop" in c for c in f.commands))

    def test_rollback_failure_is_visible_not_silently_accepted(self):
        # The actual independently tested scoped recovery raises if deletion fails.
        recovery_path = src.with_name("spamhaus_scoped_recovery.py")
        recovery_spec = importlib.util.spec_from_file_location("scoped_recovery", recovery_path)
        recovery = importlib.util.module_from_spec(recovery_spec)
        recovery_spec.loader.exec_module(recovery)
        commands = []
        def failed_delete(args):
            commands.append(args)
            if args[1:4] == ["-j", "list", "tables"]:
                return ok(args, json.dumps({"nftables": [{"table": {"family": "inet", "name": "bigbird_spamhaus"}}]}))
            if args[1:] == ["delete", "table", "inet", "bigbird_spamhaus"]:
                return subprocess.CompletedProcess(args, 1, "", "simulated delete failure")
            raise AssertionError(args)
        with self.assertRaises(RuntimeError):
            recovery.recover(runner=failed_delete, execute=True)
        self.assertTrue(any(args[1:4] == ["delete", "table", "inet"] for args in commands))

if __name__ == "__main__":
    unittest.main()
