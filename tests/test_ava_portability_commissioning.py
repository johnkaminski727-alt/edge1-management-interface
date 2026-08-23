from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CommissioningGuardrailTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_ava_service_is_loopback_read_only_and_immutable(self):
        unit = self.read("deploy/systemd/wwcx-ava-office.service")
        self.assertIn("/opt/wwcx-ava-office/current/ava_office_manager_server.py", unit)
        self.assertIn("--host 127.0.0.1 --port 8116", unit)
        self.assertIn("IPAddressDeny=any", unit)
        self.assertIn("IPAddressAllow=localhost", unit)
        self.assertIn("ReadOnlyPaths=/opt/wwcx-ava-office /var/lib/wwcx-ava-office-manager", unit)
        self.assertNotIn("/opt/edge1-management-interface/server/", unit)
        self.assertNotIn("0.0.0.0", unit)

    def test_portability_service_is_loopback_read_only_and_immutable(self):
        unit = self.read("deploy/systemd/wwcx-number-portability.service")
        self.assertIn("/opt/wwcx-number-portability/current/number_portability_server.py", unit)
        self.assertIn("--host 127.0.0.1 --port 8117", unit)
        self.assertIn("IPAddressDeny=any", unit)
        self.assertIn("IPAddressAllow=localhost", unit)
        self.assertIn("ReadOnlyPaths=/opt/wwcx-number-portability /var/lib/wwcx-portability", unit)
        self.assertNotIn("/opt/edge1-management-interface/server/", unit)
        self.assertNotIn("0.0.0.0", unit)

    def test_installers_require_pinned_clean_checkout_and_publish_immutable_release(self):
        expectations = {
            "deploy/ava-office/commission-read-only.sh": "/opt/wwcx-ava-office",
            "deploy/number-portability/commission-read-only.sh": "/opt/wwcx-number-portability",
        }
        for relative, runtime_root in expectations.items():
            script = self.read(relative)
            self.assertIn("--apply requires --expected-commit=SHA", script)
            self.assertIn("apply requires a clean checkout", script)
            self.assertIn("main or a detached exact-commit checkout", script)
            self.assertIn("expected commit mismatch", script)
            self.assertIn('git -c safe.directory="$REPO_ROOT"', script)
            self.assertIn(runtime_root, script)
            self.assertIn('RELEASE="$RELEASES/$HEAD"', script)
            self.assertIn('mv -Tf "$CURRENT.new" "$CURRENT"', script)
            self.assertIn('readlink -f "$CURRENT"', script)
            self.assertIn("systemd-analyze verify", script)
            self.assertIn("loopback listener", script)
            self.assertIn("Dry run only. No files or services changed.", script)

    def test_ava_runtime_packages_protected_call_archive_adapter(self):
        script = self.read("deploy/ava-office/commission-read-only.sh")
        self.assertIn('server/ava_call_archive.py', script)
        self.assertIn('$RELEASE/ava_call_archive.py', script)
        self.assertIn('cmp -s "$REPO_ROOT/server/ava_call_archive.py" "$RELEASE/ava_call_archive.py"', script)
        self.assertIn('"$RELEASE/ava_call_archive.py" > "$EVIDENCE/installed-files.sha256"', script)

    def test_bridge_allows_only_main_or_pinned_detached_checkout(self):
        script = self.read("deploy/activate-office-portability-operations-bridge.sh")
        self.assertIn("main or a detached exact-commit checkout", script)
        self.assertIn("expected commit mismatch", script)
        self.assertIn("apply requires clean working tree", script)
        self.assertIn('git -c safe.directory="$ROOT"', script)
        self.assertNotIn("git config --global", script)

    def test_commissioning_does_not_enable_external_action_planes(self):
        combined = (
            self.read("deploy/ava-office/commission-read-only.sh")
            + self.read("deploy/number-portability/commission-read-only.sh")
            + self.read("deploy/activate-office-portability-operations-bridge.sh")
        )
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
