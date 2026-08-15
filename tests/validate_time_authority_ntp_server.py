#!/usr/bin/env python3
"""Validate the guarded WW.CX public NTP server deployment package."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "modules" / "time-authority" / "config" / "edge1-chrony.conf"
PREFLIGHT = ROOT / "deploy" / "time-authority-ntp-server-edge1-preflight.sh"
INSTALLER = ROOT / "deploy" / "install-time-authority-ntp-server-edge1.sh"
SMOKE = ROOT / "deploy" / "time-authority-ntp-server-edge1-smoke-test.sh"
FIREWALL = ROOT / "deploy" / "publish-time-authority-ntp-firewall-edge1.sh"
RUNBOOK = ROOT / "docs" / "handoff" / "public-ntp-server-runbook.md"


def main() -> int:
    for path in (CONFIG, PREFLIGHT, INSTALLER, SMOKE, FIREWALL, RUNBOOK):
        assert path.is_file(), f"missing public NTP asset: {path.relative_to(ROOT)}"

    config = CONFIG.read_text(encoding="utf-8")
    for source in (
        "sth1.ntp.se",
        "sth2.ntp.se",
        "mmo1.ntp.se",
        "time.nist.gov",
        "time.cloudflare.com",
    ):
        assert f"server {source} iburst" in config
    for directive in (
        "minsources 3",
        "port 123",
        "allow 0/0",
        "allow ::/0",
        "ratelimit interval 1 burst 8 leak 2",
        "clientloglimit 1048576",
        "cmdport 0",
        "makestep 1.0 3",
        "rtcsync",
    ):
        assert directive in config, directive
    assert "local stratum" not in config
    assert "local orphan" not in config

    preflight = PREFLIGHT.read_text(encoding="utf-8")
    assert "UDP/123" in preflight
    assert "systemd-timesyncd" in preflight
    assert "apt-cache show chrony" in preflight
    assert "ss -H -lun 'sport = :123'" in preflight
    assert "awk '{print $5}'" not in preflight
    assert "No package, clock-service, firewall, DNS, or listener changes were made." in preflight

    installer = INSTALLER.read_text(encoding="utf-8")
    assert "WWCX_NTP_APPROVE_CLOCK_DAEMON_CUTOVER" in installer
    assert "WWCX_NTP_APPROVE_PUBLIC_UDP123" in installer
    assert "apt-get install -y chrony" in installer
    assert "disable --now systemd-timesyncd.service" in installer
    assert "systemctl restart chrony.service" in installer
    assert "chronyc waitsync" in installer
    assert "wwcx-deployment-evidence/public-ntp-server" in installer
    assert "ss -H -lun 'sport = :123'" in installer
    assert "awk '{print $5}'" not in installer
    assert "DNS publication and perimeter firewall exposure must be handled as separate approved production changes." in installer

    smoke = SMOKE.read_text(encoding="utf-8")
    assert '"server_name": "127.0.0.1"' in smoke
    assert '"port": 123' in smoke
    assert "response_mode" in smoke
    assert "leap_indicator" in smoke
    assert "chronyc tracking" in smoke
    assert "chronyc sources -v" in smoke

    firewall = FIREWALL.read_text(encoding="utf-8")
    for required in (
        "WWCX_NTP_APPROVE_PUBLIC_UDP123",
        "89.147.109.253",
        "wwcx:public-ntp-v4",
        "nft -c -f",
        "LIVE_BATCH=\"$EVIDENCE_DIR/live-insert.nft\"",
        "insert rule inet wwcxfw input position %s ip daddr %s udp dport 123 accept comment \"%s\"",
        "nft -c -f \"$LIVE_BATCH\"",
        "nft -f \"$LIVE_BATCH\"",
        "ip daddr $PUBLIC_IP udp dport 123 accept",
        "nftables.service reload: intentionally not performed",
        "live-ruleset.before.nft",
        "nftables.conf.before",
        "IPv6 firewall publication: not changed",
    ):
        assert required in firewall, required
    assert "nft insert rule inet wwcxfw input position" not in firewall
    assert 'comment "$RULE_COMMENT"' not in firewall
    assert "systemctl reload nftables" not in firewall
    assert "nft -f /etc/nftables.conf" not in firewall

    runbook = RUNBOOK.read_text(encoding="utf-8")
    assert "ntp.ww.cx" in runbook
    assert "UDP/123" in runbook
    assert "systemd-timesyncd" in runbook
    assert "chronyd" in runbook
    assert "DNS" in runbook
    assert "firewall" in runbook.lower()
    assert "sudo chronyc tracking" in runbook
    assert "sudo chronyc sources -v" in runbook
    assert "sudo chronyc clients" in runbook
    assert "506 Cannot talk to daemon" in runbook
    assert "cmdport 0" in runbook

    print("public NTP server deployment validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
