from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
TARGET = "https://ww.cx/time/"
DEFAULT_POLICY = (ROOT / "deploy" / "front-door" / "wwcx-edge1-default-http-front-door.conf").read_text()
NAMED_POLICY = (ROOT / "deploy" / "control-surfaces" / "wwcx-edge1-control-surfaces.conf").read_text()
INSTALLER = (ROOT / "deploy" / "front-door" / "install-edge1-default-http-front-door.sh").read_text()


def request_uri_pattern(policy: str) -> re.Pattern[str]:
    match = re.search(r"RewriteCond %\{REQUEST_URI\} (\S+)", policy)
    if not match:
        raise AssertionError("REQUEST_URI rewrite condition not found")
    return re.compile(match.group(1))


class Edge1FrontDoorApachePolicyTests(unittest.TestCase):
    def test_named_edge1_root_redirects_to_canonical_time_service(self):
        self.assertIn(r"RewriteCond %{HTTP_HOST} ^edge1\.ww\.cx$ [NC]", NAMED_POLICY)
        self.assertIn(TARGET, NAMED_POLICY)
        self.assertNotIn("https://creekco.ca/time/", NAMED_POLICY)
        self.assertNotIn("https://edge1.ww.cx/", NAMED_POLICY)

    def test_default_http_policy_is_root_only(self):
        pattern = request_uri_pattern(DEFAULT_POLICY)
        for path in ("/", "/index.html"):
            self.assertIsNotNone(pattern.fullmatch(path), path)
        for path in (
            "/vpn/",
            "/edge1-status/",
            "/edge1-ops/",
            "/api/operations/",
            "/mcp/wwcx-timekeeping",
            "/api/electrum-watch/healthz",
            "/admin/",
            "/ucp/",
            "/.well-known/acme-challenge/token",
            "/anything-else",
        ):
            self.assertIsNone(pattern.fullmatch(path), path)

    def test_named_policy_is_root_only(self):
        pattern = request_uri_pattern(NAMED_POLICY)
        for path in ("/", "/index.html"):
            self.assertIsNotNone(pattern.fullmatch(path), path)
        for path in (
            "/edge1-status/",
            "/api/operations/",
            "/mcp/wwcx-timekeeping/healthz",
            "/api/electrum-watch/v1/wallet/info",
            "/admin/",
            "/ucp/",
            "/.well-known/acme-challenge/token",
        ):
            self.assertIsNone(pattern.fullmatch(path), path)

    def test_redirect_target_is_exact_and_non_looping(self):
        for policy in (DEFAULT_POLICY, NAMED_POLICY):
            rules = [line for line in policy.splitlines() if line.lstrip().startswith("RewriteRule")]
            self.assertTrue(any(TARGET in line and "R=302" in line for line in rules))
            self.assertFalse(any("89.147.109.253" in line for line in rules))
            self.assertFalse(any("edge1.ww.cx" in line for line in rules))

    def test_default_policy_is_not_a_proxy_or_internal_exposure(self):
        for token in ("ProxyPass", "127.0.0.1", "localhost", "[P]", "[P,", ",P]"):
            self.assertNotIn(token, DEFAULT_POLICY)

    def test_installer_targets_only_default_http_vhost_and_is_reversible(self):
        for token in (
            "/etc/apache2/sites-available/000-default.conf",
            "/etc/apache2/sites-enabled/000-default.conf",
            "ServerName[[:space:]]+default\\.invalid",
            "/var/backups/wwcx-edge1-front-door-",
            "apache2ctl configtest",
            "systemctl reload apache2",
            "rollback.sh",
            "SHA256SUMS",
        ):
            self.assertIn(token, INSTALLER)
        for token in (
            "systemctl restart apache2",
            "a2dissite",
            "a2ensite",
            "nft ",
            "iptables ",
            "certbot",
            "fwconsole",
            "asterisk -rx",
            "chronyc",
            "git reset",
            "git checkout",
        ):
            self.assertNotIn(token, INSTALLER)


if __name__ == "__main__":
    unittest.main()
