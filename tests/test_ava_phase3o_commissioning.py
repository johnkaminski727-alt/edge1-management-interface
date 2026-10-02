from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class AvaPhase3OCommissioningTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_gateway_unit_uses_immutable_release_and_loopback_boundary(self):
        unit = self.read("deploy/systemd/bigbird-ai-gateway.service")
        self.assertIn("WorkingDirectory=/opt/bigbird-ai-gateway/current", unit)
        self.assertIn("ExecStart=/usr/bin/python3 /opt/bigbird-ai-gateway/current/app/main.py", unit)
        self.assertIn("EDGE1_MANAGEMENT_ROOT=/opt/bigbird-ai-gateway/current", unit)
        self.assertIn("IPAddressDeny=any", unit)
        self.assertIn("IPAddressAllow=localhost", unit)
        self.assertNotIn("/opt/edge1-management-interface/services/", unit)

    def test_worker_unit_uses_immutable_release(self):
        unit = self.read("deploy/private-ai-browser-worker.service")
        self.assertIn("WorkingDirectory=/opt/wwcx-private-ai-browser-worker/current", unit)
        self.assertIn(
            "ExecStart=/usr/bin/python3 /opt/wwcx-private-ai-browser-worker/current/private_ai_browser_worker.py",
            unit,
        )
        self.assertNotIn("/opt/edge1-management-interface/server/", unit)

    def test_gateway_and_worker_installers_are_pinned_dry_run_by_default(self):
        expectations = {
            "deploy/install-ava-readonly-gateway.sh": "/opt/bigbird-ai-gateway",
            "deploy/install-ava-browser-worker.sh": "/opt/wwcx-private-ai-browser-worker",
        }
        for relative, runtime_root in expectations.items():
            script = self.read(relative)
            self.assertIn("MODE=dry-run", script)
            self.assertIn("--apply requires --expected-commit=SHA", script)
            self.assertIn("expected commit mismatch", script)
            self.assertIn("apply requires a clean checkout", script)
            self.assertIn("main or a detached exact-commit checkout", script)
            self.assertIn('git -c safe.directory="$REPO_ROOT"', script)
            self.assertIn(runtime_root, script)
            self.assertIn('RELEASE="$RELEASES/$HEAD"', script)
            self.assertIn('mv -Tf "$CURRENT.new" "$CURRENT"', script)
            self.assertIn('readlink -f "$CURRENT"', script)
            self.assertIn("systemd-analyze verify", script)
            self.assertIn("Dry run only. No files or services changed.", script)
            self.assertIn("[ -e \"$RELEASE\" ]", script)
            self.assertNotIn("git reset", script)
            self.assertNotIn("git checkout", script)
            self.assertNotIn("git pull", script)

    def test_gateway_installer_packages_current_contacts_boundary(self):
        script = self.read("deploy/install-ava-readonly-gateway.sh")
        for required in (
            "services/bigbird-ai-gateway/app/main.py",
            "services/bigbird-ai-gateway/app/library_engine.py",
            "server/ava_contacts_gateway.py",
            "server/phone_intelligence_gateway.py",
        ):
            self.assertIn(required, script)
        self.assertIn("loopback listener 8787 not found", script)
        self.assertIn("Provider egress remains a separate explicit drop-in decision.", script)

    def test_worker_installer_never_invents_queue_identity(self):
        script = self.read("deploy/install-ava-browser-worker.sh")
        self.assertIn("no reusable WW.CX queue worker identity is present", script)
        self.assertIn("BB_RELAY_SECRET", script)
        self.assertIn("BB_BROWSER_WORKER_SECRET", script)
        self.assertNotIn("secrets.token_hex", script)
        self.assertNotIn("echo $BB_RELAY", script)

    def test_private_library_bootstrap_is_pinned_and_rollback_safe(self):
        script = self.read("deploy/install-bigbird-private-library-runtime.sh")
        self.assertIn("MODE=dry-run", script)
        self.assertIn("--apply requires --expected-commit=SHA", script)
        self.assertIn("apply requires a clean checkout", script)
        self.assertIn("library.sqlite3.before", script)
        self.assertIn("PRAGMA integrity_check", script)
        self.assertIn("Dry run only. No files or services changed.", script)
        self.assertNotIn("/opt/edge1-management-interface", script)

    def test_commissioning_does_not_publish_control_center_or_promote_ava(self):
        combined = (
            self.read("deploy/install-ava-readonly-gateway.sh")
            + self.read("deploy/install-ava-browser-worker.sh")
            + self.read("deploy/install-bigbird-private-library-runtime.sh")
        )
        for forbidden in (
            "/var/www/edge1-status",
            "navigation_registry.json",
            "browser_route",
            "nginx",
            "operator-shell",
        ):
            self.assertNotIn(forbidden, combined)


if __name__ == "__main__":
    unittest.main()
