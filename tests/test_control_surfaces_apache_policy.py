from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
POLICY = (ROOT / "deploy" / "control-surfaces" / "wwcx-edge1-control-surfaces.conf").read_text()
INSTALLER = (ROOT / "deploy" / "control-surfaces" / "install-edge1-control-surfaces-apache.sh").read_text()


class ControlSurfacesApachePolicyTests(unittest.TestCase):
    def test_public_root_redirect_is_narrow(self):
        self.assertIn(r"RewriteCond %{HTTP_HOST} ^edge1\.ww\.cx$ [NC]", POLICY)
        self.assertIn(r"RewriteCond %{REQUEST_URI} ^/(?:index\.html)?$ [NC]", POLICY)
        self.assertIn("https://ww.cx/time/", POLICY)
        self.assertNotIn("https://creekco.ca/time/", POLICY)

    def test_freepbx_surfaces_are_private(self):
        self.assertIn('<LocationMatch "^/(?:admin|ucp)(?:/|$)">', POLICY)
        for network in (
            "127.0.0.1",
            "::1",
            "10.77.0.0/24",
            "100.64.0.0/10",
            "fd7a:115c:a1e0::/48",
        ):
            self.assertIn(f"Require ip {network}", POLICY)
        self.assertNotIn("Require all granted", POLICY)

    def test_installer_is_reversible_and_apache_only(self):
        for token in (
            "--check|--apply",
            "/var/backups/wwcx-edge1-control-surfaces-",
            "apache2ctl configtest",
            "systemctl reload apache2",
            "rollback.sh",
            "SHA256SUMS",
        ):
            self.assertIn(token, INSTALLER)
        for token in (
            "nft ",
            "iptables ",
            "fwconsole",
            "asterisk -rx",
            "kamcmd",
            "git reset",
            "git checkout",
        ):
            self.assertNotIn(token, INSTALLER)


if __name__ == "__main__":
    unittest.main()
