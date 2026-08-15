#!/usr/bin/env python3
"""Validate the guarded WW.CX public NTP server deployment package."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "modules" / "time-authority" / "config" / "edge1-chrony.conf"
PREFLIGHT = ROOT / "deploy" / "time-authority-ntp-server-edge1-preflight.sh"
INSTALLER = ROOT / "deploy" / "install-time-authority-ntp-server-edge1.sh"
SMOKE = ROOT / "deploy" / "time-authority-ntp-server-edge1-smoke-test.sh"
RUNBOOK = ROOT / "docs" / "handoff" / "public-ntp-server-runbook.md"


def main() -> int:
    for path in (CONFIG, PREFLIGHT, INSTALLER, SMOKE, RUNBOOK):
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
    assert "No package, clock-service, firewall, DNS, or listener changes were made." in preflight

    installer = INSTALLER.read_text(encoding="utf-8")
    assert "WWCX_NTP_APPROVE_CLOCK_DAEMON_CUTOVER" in installer
    assert "WWCX_NTP_APPROVE_PUBLIC_UDP123" in installer
    assert "apt-get install -y chrony" in installer
    assert "disable --now systemd-timesyncd.service" in installer
    assert "systemctl restart chrony.service" in installer
    assert "chronyc waitsync" in installer
    assert "wwcx-deployment-evidence/public-ntp-server" in installer
    assert "DNS publication and perimeter firewall exposure must be handled as separate approved production changes." in installer

    smoke = SMOKE.read_text(encoding="utf-8")
    assert '"server_name": "127.0.0.1"' in smoke
    assert '"port": 123' in smoke
    assert "response_mode" in smoke
    assert "leap_indicator" in smoke
    assert "chronyc tracking" in smoke
    assert "chronyc sources -v" in smoke

    runbook = RUNBOOK.read_text(encoding="utf-8")
    assert "ntp.ww.cx" in runbook
    assert "UDP/123" in runbook
    assert "systemd-timesyncd" in runbook
    assert "chronyd" in runbook
    assert "DNS" in runbook
    assert "firewall" in runbook.lower()

    print("public NTP server deployment validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
