import importlib.util
import pathlib
import unittest
from unittest import mock

MODULE_PATH = pathlib.Path(__file__).parents[1] / "server" / "control_surface_diagnostics.py"
spec = importlib.util.spec_from_file_location("control_surface_diagnostics", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def fake_result(*, status="ok", stdout="", stderr="", available=True, exit_code=0):
    return {
        "available": available,
        "status": status,
        "exit_code": exit_code,
        "duration_ms": 1,
        "stdout": stdout,
        "stderr": stderr,
    }


PASSIVE_SS = "\n".join([
    "udp UNCONN 0 0 127.0.0.1:5061 0.0.0.0:*",
    "tcp LISTEN 0 128 127.0.0.1:8088 0.0.0.0:*",
    "tcp LISTEN 0 128 127.0.0.1:8089 0.0.0.0:*",
    "udp UNCONN 0 0 127.0.0.1:5060 0.0.0.0:*",
    "udp UNCONN 0 0 89.147.109.253:5060 0.0.0.0:*",
])


def privilege_gated_run(argv, timeout=20):
    del timeout
    command = argv[0]
    if command == "asterisk":
        return fake_result(status="failed", stderr="control socket permission denied", exit_code=1)
    if command == "kamcmd":
        return fake_result(status="failed", stderr="control socket permission denied", exit_code=255)
    if command == "fwconsole":
        return fake_result(status="command_unavailable", available=False, exit_code=None)
    if argv[:2] == ("pgrep", "-x"):
        return fake_result(stdout="123\n")
    if argv[:4] == ("ss", "-H", "-lntu"):
        return fake_result(stdout=PASSIVE_SS)
    if command == "curl":
        if argv[-1].endswith("/admin/"):
            return fake_result(stdout="302")
        if argv[-1].endswith("/ucp/"):
            return fake_result(stdout="200")
    raise AssertionError(f"unexpected fixed command: {argv!r}")


class ControlSurfaceDiagnosticsTests(unittest.TestCase):
    def test_fixed_profiles_do_not_invoke_shell(self):
        expected = {"asterisk", "kamailio", "freepbx"}
        self.assertEqual(set(mod.PROFILES), expected)
        for profile, checks in mod.PROFILES.items():
            self.assertTrue(checks, profile)
            for name, argv in checks:
                self.assertIsInstance(name, str)
                self.assertIsInstance(argv, tuple)
                self.assertNotIn("sh", argv[:1])
                self.assertNotIn("bash", argv[:1])
                self.assertTrue(all(isinstance(item, str) and item for item in argv))

    def test_parser_classifies_control_and_peering_surfaces(self):
        cases = [
            (
                'tcp LISTEN 0 128 0.0.0.0:22 0.0.0.0:* users:(("sshd",pid=1,fd=3))',
                "private-control",
                "wildcard",
            ),
            (
                'tcp LISTEN 0 128 127.0.0.1:8787 0.0.0.0:* users:(("python3",pid=2,fd=4))',
                "internal-service",
                "loopback",
            ),
            (
                'udp UNCONN 0 0 0.0.0.0:5060 0.0.0.0:* users:(("kamailio",pid=3,fd=5))',
                "peering",
                "wildcard",
            ),
            (
                'tcp LISTEN 0 128 0.0.0.0:8089 0.0.0.0:* users:(("asterisk",pid=4,fd=6))',
                "private-control",
                "wildcard",
            ),
            (
                'tcp LISTEN 0 128 192.0.2.10:9000 0.0.0.0:* users:(("mystery",pid=5,fd=7))',
                "unknown-needs-attribution",
                "specific",
            ),
        ]
        for line, expected_class, expected_exposure in cases:
            with self.subTest(line=line):
                row = mod.parse_ss_line(line)
                self.assertIsNotNone(row)
                self.assertEqual(row["classification"], expected_class)
                self.assertEqual(row["exposure"], expected_exposure)

    def test_clean_redacts_secrets(self):
        cleaned = mod.clean("password=abc123 token:xyz Authorization: BearerValue")
        self.assertNotIn("abc123", cleaned)
        self.assertNotIn("xyz", cleaned)
        self.assertNotIn("BearerValue", cleaned)
        self.assertIn("[REDACTED]", cleaned)

    def test_summary_contract_has_all_required_classes(self):
        required = {
            "public-infrastructure",
            "peering",
            "private-control",
            "internal-service",
            "unknown-needs-attribution",
        }
        self.assertEqual(set(mod.summary()["classification_contract"]), required)
        self.assertTrue(mod.summary()["read_only"])
        self.assertFalse(mod.summary()["parameters_accepted"])
        self.assertTrue(all(item["passive_fallback_available"] for item in mod.summary()["components"].values()))

    def test_privilege_gated_native_diagnostics_fall_back_to_limited_passive_evidence(self):
        expected_native = {
            "asterisk": "error",
            "kamailio": "error",
            "freepbx": "unavailable",
        }
        with mock.patch.object(mod, "run_fixed", side_effect=privilege_gated_run):
            for profile in ("asterisk", "kamailio", "freepbx"):
                with self.subTest(profile=profile):
                    result = mod.component(profile)
                    self.assertEqual(result["status"], "limited")
                    self.assertEqual(result["native_cli_status"], expected_native[profile])
                    self.assertEqual(result["passive_fallback"]["status"], "ok")
                    self.assertTrue(result["read_only"])

    def test_passive_fallbacks_do_not_request_privilege_escalation_or_shell(self):
        calls = []

        def recording_run(argv, timeout=20):
            calls.append(argv)
            return privilege_gated_run(argv, timeout)

        with mock.patch.object(mod, "run_fixed", side_effect=recording_run):
            mod.passive_asterisk()
            mod.passive_kamailio()
            mod.passive_freepbx()

        self.assertTrue(calls)
        for argv in calls:
            self.assertNotIn(argv[0], {"sudo", "su", "doas", "sh", "bash"})
        curl_urls = [argv[-1] for argv in calls if argv[0] == "curl"]
        self.assertEqual(curl_urls, ["https://edge1.ww.cx/admin/", "https://edge1.ww.cx/ucp/"])


if __name__ == "__main__":
    unittest.main()
