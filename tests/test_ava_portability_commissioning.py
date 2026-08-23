from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CommissioningGuardrailTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_ava_service_is_loopback_and_read_only(self):
        unit = self.read("deploy/systemd/wwcx-ava-office.service")
        self.assertIn("--host 127.0.0.1 --port 8116", unit)
        self.assertIn("IPAddressDeny=any", unit)
        self.assertIn("IPAddressAllow=localhost", unit)
        self.assertIn("ReadOnlyPaths=/opt/edge1-management-interface /var/lib/wwcx-ava-office-manager", unit)
        self.assertNotIn("0.0.0.0", unit)

    def test_portability_service_is_loopback_and_read_only(self):
        unit = self.read("deploy/systemd/wwcx-number-portability.service")
        self.assertIn("--host 127.0.0.1 --port 8117", unit)
        self.assertIn("IPAddressDeny=any", unit)
        self.assertIn("IPAddressAllow=localhost", unit)
        self.assertIn("ReadOnlyPaths=/opt/edge1-management-interface /var/lib/wwcx-portability", unit)
        self.assertNotIn("0.0.0.0", unit)

    def test_installers_require_pinned_clean_main_for_apply(self):
        for relative in (
            "deploy/ava-office/commission-read-only.sh",
            "deploy/number-portability/commission-read-only.sh",
        ):
            script = self.read(relative)
            self.assertIn("--apply requires --expected-commit=SHA", script)
            self.assertIn("apply requires a clean main-branch checkout", script)
            self.assertIn("expected commit mismatch", script)
            self.assertIn("systemd-analyze verify", script)
            self.assertIn("loopback listener", script)
            self.assertIn("Dry run only. No files or services changed.", script)

    def test_commissioning_does_not_enable_external_action_planes(self):
        combined = self.read("deploy/ava-office/commission-read-only.sh") + self.read("deploy/number-portability/commission-read-only.sh")
        forbidden = (
            "asterisk -rx",
            "fwconsole",
            "telephony.route",
            "number.port",
            "carrier.submit",
            "stir_shaken",
            "emergency.call",
        )
        for token in forbidden:
            self.assertNotIn(token, combined.lower())


if __name__ == "__main__":
    unittest.main()
