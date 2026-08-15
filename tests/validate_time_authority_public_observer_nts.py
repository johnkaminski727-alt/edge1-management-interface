#!/usr/bin/env python3
"""Validate the Business159 public observer and guarded Edge1 NTS package."""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "modules" / "time-authority" / "config" / "public-service-sources.json"
BASE_CONFIG = ROOT / "modules" / "time-authority" / "config" / "edge1-chrony.conf"
NTS_CONFIG = ROOT / "modules" / "time-authority" / "config" / "edge1-chrony-nts.conf"
NTS_PROBE = ROOT / "tools" / "time_authority" / "nts_ke_probe.py"
STATUS_BUILDER = ROOT / "tools" / "time_authority" / "build_public_time_status.py"
OBSERVER = ROOT / "tools" / "time_authority" / "observe-public-time-service-shared-host.sh"
OBSERVER_INSTALL = ROOT / "deploy" / "install-public-time-observer-shared-host.sh"
OBSERVER_SMOKE = ROOT / "deploy" / "public-time-observer-shared-host-smoke-test.sh"
CERT_HOST_MATCH = ROOT / "tools" / "time_authority" / "certificate-matches-hostname.sh"
CERT_DISCOVERY = ROOT / "tools" / "time_authority" / "discover-nts-certificate-edge1.sh"
NTS_PREFLIGHT = ROOT / "deploy" / "time-authority-nts-edge1-preflight.sh"
NTS_INSTALL = ROOT / "deploy" / "install-time-authority-nts-edge1.sh"
NTS_SMOKE = ROOT / "deploy" / "time-authority-nts-edge1-smoke-test.sh"
NTS_FIREWALL = ROOT / "deploy" / "publish-time-authority-nts-firewall-edge1.sh"


def read(path: Path) -> str:
    assert path.is_file(), "missing {}".format(path.relative_to(ROOT))
    return path.read_text(encoding="utf-8")


def validate_builder() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        ntp = temp / "ntp.jsonl"
        nts = temp / "nts.json"
        output = temp / "status.json"
        ntp.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "observed_at_utc": "2026-08-15T21:24:00Z",
                    "reachable": True,
                    "resolved_address": "89.147.109.253",
                    "stratum": 4,
                    "rtt_ms": 42.5,
                    "clock_offset_ms": 1.25,
                    "leap_indicator": 0,
                    "ntp_version": 4,
                    "secret": "must-not-publish",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        nts.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "observed_at_utc": "2026-08-15T21:24:01Z",
                    "reachable": True,
                    "resolved_address": "89.147.109.253",
                    "tls_verified": True,
                    "alpn": "ntske/1",
                    "rtt_ms": 51.0,
                    "certificate_not_after_utc": "2026-11-13T00:00:00Z",
                    "private_key": "must-not-publish",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        subprocess.run(
            [
                sys.executable,
                str(STATUS_BUILDER),
                "--ntp-current",
                str(ntp),
                "--nts-current",
                str(nts),
                "--output",
                str(output),
                "--nts-expected",
            ],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        payload = json.loads(output.read_text(encoding="utf-8"))
        assert payload["schema_version"] == 1
        assert payload["service"]["canonical_host"] == "ntp.ww.cx"
        assert payload["service"]["alternate_hosts"] == ["time.ww.cx"]
        assert payload["observer"]["id"] == "business159"
        assert payload["ntp"]["reachable"] is True
        assert payload["ntp"]["stratum"] == 4
        assert payload["nts"]["expected"] is True
        assert payload["nts"]["reachable"] is True
        assert payload["nts"]["tls_verified"] is True
        assert payload["nts"]["alpn"] == "ntske/1"
        rendered = json.dumps(payload)
        assert "must-not-publish" not in rendered
        assert "private_key" not in rendered
        assert "secret" not in rendered


def validate_hostname_helper() -> None:
    openssl = shutil.which("openssl")
    assert openssl, "openssl is required for certificate hostname regression validation"

    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        cert = temp / "cert.pem"
        key = temp / "key.pem"
        subprocess.run(
            [
                openssl,
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-nodes",
                "-days",
                "1",
                "-subj",
                "/CN=edge1.ww.cx",
                "-addext",
                "subjectAltName=DNS:edge1.ww.cx,DNS:pbx.ww.cx",
                "-keyout",
                str(key),
                "-out",
                str(cert),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        match = subprocess.run(
            ["sh", str(CERT_HOST_MATCH), str(cert), "edge1.ww.cx"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        mismatch = subprocess.run(
            ["sh", str(CERT_HOST_MATCH), str(cert), "ntp.ww.cx"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        assert match.returncode == 0
        assert mismatch.returncode != 0


def main() -> int:
    source = json.loads(read(SOURCE))
    assert source["schema_version"] == 1
    assert len(source["sources"]) == 1
    item = source["sources"][0]
    assert item["source_id"] == "wwcx-public-ntp"
    assert item["server_name"] == "ntp.ww.cx"
    assert item["port"] == 123
    assert item["expected_stratum_min"] == 1
    assert item["expected_stratum_max"] == 15

    base = read(BASE_CONFIG)
    assert "confdir /etc/chrony/conf.d" in base
    assert "local stratum" not in base

    nts_config = read(NTS_CONFIG)
    for directive in (
        "ntsport 4460",
        "ntsservercert /etc/chrony/nts/ntp.ww.cx-fullchain.pem",
        "ntsserverkey /etc/chrony/nts/ntp.ww.cx-privkey.pem",
        "ntsdumpdir /var/lib/chrony",
    ):
        assert directive in nts_config

    probe = read(NTS_PROBE)
    assert 'set_alpn_protocols(["ntske/1"])' in probe
    assert "ssl.create_default_context()" in probe
    assert "check_hostname = True" in probe
    assert "CERT_REQUIRED" in probe
    assert "certificate_not_after_utc" in probe

    observer = read(OBSERVER)
    assert "public-service-sources.json" in observer
    assert "public-service-measurements.jsonl" in observer
    assert "public-status.json" in observer
    assert "--nts-expected" in observer
    assert "NTP_RC" in observer
    assert "NTS_RC" in observer

    observer_install = read(OBSERVER_INSTALL)
    assert "*/5 * * * *" in observer_install
    assert "WWCX_NTS_EXPECTED" in observer_install
    assert "nts-expected" in observer_install
    assert 'sh "$REPO_ROOT/deploy/public-time-observer-shared-host-smoke-test.sh"' in observer_install

    observer_smoke = read(OBSERVER_SMOKE)
    assert 'ntp.get("reachable") is True' in observer_smoke
    assert 'nts.get("alpn") == "ntske/1"' in observer_smoke

    host_match = read(CERT_HOST_MATCH)
    assert "-checkhost" in host_match
    assert "does match certificate" in host_match
    assert "does NOT match certificate" in host_match

    discovery = read(CERT_DISCOVERY)
    assert "certificate-matches-hostname.sh" in discovery
    assert "contents_read=no" in discovery
    assert "privkey.pem" in discovery

    preflight = read(NTS_PREFLIGHT)
    for guard in (
        "WWCX_NTS_CERT_SOURCE",
        "WWCX_NTS_KEY_SOURCE",
        "+NTS",
        "certificate-matches-hostname.sh",
        "-checkend 604800",
        "cmp -s",
        "sport = :4460",
        "No certificate, chrony configuration, service, firewall, DNS, or listener changes were made.",
    ):
        assert guard in preflight

    installer = read(NTS_INSTALL)
    for guard in (
        "WWCX_NTS_APPROVE_CERTIFICATE_INSTALL",
        "WWCX_NTS_APPROVE_NTS_LISTENER",
        "refusing to overwrite an existing private key",
        "0640",
        "chronyd -p -f",
        "chronyc waitsync",
        "time-authority-nts-edge1-smoke-test.sh",
        "Perimeter TCP/4460 firewall publication is NOT performed by this installer.",
    ):
        assert guard in installer
    assert "WWCX_NTS_APPROVE_PUBLIC_TCP4460" not in installer

    smoke = read(NTS_SMOKE)
    assert "127.0.0.1" in smoke
    assert "4460" in smoke
    assert 'set_alpn_protocols(["ntske/1"])' in smoke
    assert 'server_hostname="ntp.ww.cx"' in smoke
    assert "time-authority-ntp-server-edge1-smoke-test.sh" in smoke

    firewall = read(NTS_FIREWALL)
    for guard in (
        "WWCX_NTS_APPROVE_PUBLIC_TCP4460",
        "tcp dport 4460 accept",
        "wwcx:public-nts-ke-v4",
        "nft -c -f",
        "live-insert.nft",
        "nftables.service reload: intentionally not performed",
        "verify NTS-KE and an authenticated NTS time exchange from outside Edge1",
    ):
        assert guard in firewall
    assert "systemctl reload nftables" not in firewall
    assert "nft -f /etc/nftables.conf" not in firewall

    validate_builder()
    validate_hostname_helper()
    print("public time observer and NTS deployment validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
