import importlib.util
import pathlib
import unittest

MODULE_PATH = pathlib.Path(__file__).parents[1] / "server" / "control_surface_diagnostics.py"
spec = importlib.util.spec_from_file_location("control_surface_diagnostics", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


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


if __name__ == "__main__":
    unittest.main()
