from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / "scripts" / "control-surfaces-live-inventory.sh").read_text()


class LiveInventoryContractTests(unittest.TestCase):
    def test_read_only_contract(self):
        forbidden = [
            "systemctl restart",
            "systemctl reload",
            "systemctl stop",
            "systemctl start",
            "nft add",
            "nft delete",
            "nft flush",
            "iptables -A",
            "iptables -D",
            "iptables -F",
            "a2ensite",
            "a2dissite",
            "fwconsole reload",
            "fwconsole restart",
            "git reset",
            "git checkout",
            "git clean",
            "git pull",
            "git fetch",
            "curl -X POST",
            "curl --data",
            "eval ",
            "sh -c",
            "bash -c",
            "> /etc/",
        ]
        for token in forbidden:
            self.assertNotIn(token, SCRIPT, token)

    def test_required_inventory_domains(self):
        required = [
            "ss -H -lntup",
            "apache2ctl -S",
            "apache2ctl configtest",
            "nft list ruleset",
            "wg show",
            "pjsip show endpoints",
            "pjsip show transports",
            "pjsip show registrations",
            "http show status",
            "manager show settings",
            "ari show status",
            "rtp show settings",
            "kamcmd core.version",
            "kamcmd core.uptime",
            "kamcmd core.ps",
            "fwconsole status",
            "ip -brief address",
            "ip route show table all",
            "resolvectl status",
            "127.0.0.1:8097",
            "127.0.0.1:8787",
            "/opt/edge1-management-interface",
            "/opt/bigbird-ai-gateway",
        ]
        for token in required:
            self.assertIn(token, SCRIPT, token)

    def test_sensitive_output_controls(self):
        for token in [
            "Set-Cookie:",
            "Authorization:",
            "password|passwd|secret|token",
            "private[_-]?key",
            "preshared[_-]?key",
            "https?://",
            "access_token",
            "umask 077",
        ]:
            self.assertIn(token, SCRIPT, token)
        self.assertIn("ps -eo pid,user,comm", SCRIPT)
        self.assertNotIn("ps -eo pid,user,comm,args", SCRIPT)

    def test_no_secret_configuration_reads(self):
        forbidden_paths = [
            "/etc/asterisk/pjsip.conf",
            "/etc/asterisk/manager.conf",
            "/etc/asterisk/ari.conf",
            "/etc/freepbx.conf",
            "/etc/wireguard/",
            ".env",
        ]
        for path in forbidden_paths:
            self.assertNotIn(path, SCRIPT, path)

    def test_evidence_is_private_and_hashed(self):
        self.assertIn("umask 077", SCRIPT)
        self.assertIn("SHA256SUMS", SCRIPT)
        self.assertIn(".local/state/edge1-control-surfaces/evidence", SCRIPT)


if __name__ == "__main__":
    unittest.main()
