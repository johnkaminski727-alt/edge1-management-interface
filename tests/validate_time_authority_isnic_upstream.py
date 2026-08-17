#!/usr/bin/env python3
"""Validate the WW.CX Edge1 ISNIC upstream rollout package."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRAGMENT = ROOT / "modules" / "time-authority" / "config" / "wwcx-isnic-upstream.conf"
INSTALLER = ROOT / "deploy" / "install-time-authority-isnic-upstream-edge1.sh"
BASE_CONFIG = ROOT / "modules" / "time-authority" / "config" / "edge1-chrony.conf"
EVIDENCE = ROOT / "docs" / "handoff" / "iceland-time-source-live-evidence-20260817.md"


def main() -> int:
    for path in (FRAGMENT, INSTALLER, BASE_CONFIG, EVIDENCE):
        assert path.is_file(), f"missing ISNIC rollout asset: {path.relative_to(ROOT)}"

    fragment = FRAGMENT.read_text(encoding="utf-8")
    assert "server ht-time01.isnic.is iburst" in fragment
    assert "mh-time01.isnic.is" not in fragment
    assert " prefer" not in fragment

    base = BASE_CONFIG.read_text(encoding="utf-8")
    assert "confdir /etc/chrony/conf.d" in base
    assert "minsources 3" in base
    for source in (
        "sth1.ntp.se",
        "sth2.ntp.se",
        "mmo1.ntp.se",
        "time.nist.gov",
        "time.cloudflare.com",
    ):
        assert f"server {source} iburst" in base

    installer = INSTALLER.read_text(encoding="utf-8")
    for required in (
        "WWCX_TIME_APPROVE_ISNIC_UPSTREAM",
        "ht-time01.isnic.is",
        "/etc/chrony/conf.d/wwcx-isnic-upstream.conf",
        "ntp_rtt_probe.py",
        "expected_stratum\": 1",
        "systemctl restart chrony.service",
        "chronyc waitsync",
        "chronyc -N sources -v",
        "Leap status     : Normal",
        "time-authority-ntp-server-edge1-smoke-test.sh",
        "ALPN protocol: ntske/1",
        "isnic-upstream-$STAMP",
        "ROLLBACK: restoring previous ISNIC fragment state",
        "No DNS or firewall change was made.",
    ):
        assert required in installer, required

    for forbidden in (
        "nft ",
        "iptables",
        "firewall-cmd",
        "certbot",
        "prefer ht-time01",
        "server mh-time01.isnic.is",
    ):
        assert forbidden not in installer, forbidden

    evidence = EVIDENCE.read_text(encoding="utf-8")
    assert "20/20" in evidence
    assert "0.7975 ms" in evidence
    assert "0.015 ms" in evidence
    assert "retain `minsources 3`" in evidence
    assert "do not set `prefer`" in evidence

    print("ISNIC upstream rollout validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
