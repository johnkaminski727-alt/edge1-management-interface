#!/usr/bin/env python3
"""Validate guarded certificate issuance and renewal lifecycle assets for WW.CX NTS."""

import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ISSUE = ROOT / "deploy" / "issue-time-authority-nts-certificate-edge1.sh"
HOOK = ROOT / "deploy" / "time-authority-nts-certbot-deploy-hook.sh"
HOOK_INSTALL = ROOT / "deploy" / "install-time-authority-nts-renewal-hook-edge1.sh"


def read(path: Path) -> str:
    assert path.is_file(), "missing {}".format(path.relative_to(ROOT))
    return path.read_text(encoding="utf-8")


def main() -> int:
    issue = read(ISSUE)
    for required in (
        "WWCX_NTS_APPROVE_CERTIFICATE_ISSUANCE",
        "certbot certonly",
        "--apache",
        "--non-interactive",
        '--cert-name "$CERT_NAME"',
        "--key-type ecdsa",
        'HOSTNAME_TO_ISSUE=${WWCX_NTS_HOSTNAME:-ntp.ww.cx}',
        "certificate-matches-hostname.sh",
        "discover-nts-certificate-edge1.sh",
        "time-authority-ntp-server-edge1-smoke-test.sh",
        "Certificate was NOT installed into chronyd by this helper.",
        "TCP/4460 firewall state was NOT changed.",
    ):
        assert required in issue
    assert "--agree-tos" not in issue
    assert "systemctl restart chrony" not in issue
    assert "nft " not in issue

    hook = read(HOOK)
    for required in (
        'EXPECTED_LINEAGE=${WWCX_NTS_CERTBOT_LINEAGE:-/etc/letsencrypt/live/ntp.ww.cx}',
        '[ "$LINEAGE" = "$EXPECTED_LINEAGE" ] || exit 0',
        "does match certificate",
        "does NOT match certificate",
        "checkend 604800",
        "cmp -s",
        "0640",
        "systemctl restart chrony.service",
        "chronyc waitsync",
        "sport = :123",
        "sport = :4460",
        "TLS_RC",
        "ALPN protocol: ntske/1",
        "Verify return code: 0 (ok)",
        "rollback_and_fail",
    ):
        assert required in hook

    installer = read(HOOK_INSTALL)
    for required in (
        "WWCX_NTS_APPROVE_RENEWAL_HOOK_INSTALL",
        "/etc/letsencrypt/renewal-hooks/deploy/50-wwcx-ntp-chrony-nts",
        "chronyd NTS-KE listener is not active on TCP/4460",
        "manual review required before replacement",
        "sh -n",
        "not-ntp.ww.cx",
        "controlled renewal/deploy-hook validation remains required",
    ):
        assert required in installer

    env = dict(os.environ)
    env["RENEWED_LINEAGE"] = "/etc/letsencrypt/live/unrelated.example"
    env["RENEWED_DOMAINS"] = "unrelated.example"
    result = subprocess.run(
        ["sh", str(HOOK)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert result.stderr == ""

    print("NTS certificate issuance and renewal lifecycle validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
