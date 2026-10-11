#!/usr/bin/env python3
"""ENG-023: reviewed non-loopback listeners are only downgraded while live checks hold."""
import importlib.util, json, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location("api_surface_health_bot", ROOT / "tools/automation/api_surface_health_bot.py")
BOT = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(BOT)

RULE = "-A ufw-user-input -i wg-edge2 -p tcp -d 10.78.0.2 --dport 8140 -s 10.78.0.1 -j ACCEPT"

class AcceptedExposureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); d = Path(self.tmp.name)
        self.inv = d / "inv.json"; self.state = d / "state.json"; self.acc = d / "acc.json"; self.ufw = d / "user.rules"
        self.inv.write_text(json.dumps({"live_apis": [{"port": 8140, "bind_scope": "network", "service": "x.service",
                                                       "process": "python3", "exposure": "network_listener", "access_boundary": "read_only"}]}))
        self.acc.write_text(json.dumps({"accepted": [{"port": 8140, "service": "x.service", "bind_address": "10.78.0.2",
                                                      "ufw_rule": RULE, "reason": "test"}]}))
        self.ufw.write_text("*filter\n" + RULE + "\nCOMMIT\n")
        BOT.active = lambda unit: "active"

    def run_build(self, addrs, accepted=True, rule=True):
        if not accepted: self.acc.write_text(json.dumps({"accepted": []}))
        if not rule: self.ufw.write_text("*filter\nCOMMIT\n")
        d = BOT.build(self.inv, self.state, self.acc, self.ufw, listen=lambda port: set(addrs))
        return {f["kind"]: f for f in d["findings"]}, d

    def test_exact_bind_and_rule_is_info(self):
        kinds, d = self.run_build({"10.78.0.2"})
        self.assertEqual(kinds["accepted_exposure"]["severity"], "info")
        self.assertNotIn("unexpected_exposure", kinds); self.assertEqual(d["summary"]["high"], 0)

    def test_wildcard_bind_stays_high(self):
        kinds, _ = self.run_build({"0.0.0.0"})
        self.assertEqual(kinds["unexpected_exposure"]["severity"], "high")
        self.assertIn("exception_check_failed", kinds["unexpected_exposure"]["detail"])

    def test_extra_bind_stays_high(self):
        kinds, _ = self.run_build({"10.78.0.2", "0.0.0.0"})
        self.assertIn("unexpected_exposure", kinds)

    def test_missing_ufw_rule_stays_high(self):
        kinds, _ = self.run_build({"10.78.0.2"}, rule=False)
        self.assertIn("ufw_rule_missing", kinds["unexpected_exposure"]["detail"])

    def test_unlisted_listener_stays_high(self):
        kinds, _ = self.run_build({"10.78.0.2"}, accepted=False)
        self.assertEqual(kinds["unexpected_exposure"]["severity"], "high")

    def test_not_listening_stays_high(self):
        kinds, _ = self.run_build(set())
        self.assertIn("unexpected_exposure", kinds)

    def test_proc_address_decoding(self):
        self.assertEqual(BOT._proc_addr("02004E0A"), "10.78.0.2")
        self.assertEqual(BOT._proc_addr("00000000"), "0.0.0.0")

if __name__ == "__main__":
    unittest.main()
