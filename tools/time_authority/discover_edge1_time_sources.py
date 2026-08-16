#!/usr/bin/env python3
"""Read-only discovery probe for better Edge1 time sources.

The probe intentionally does not change chrony, firewall, routing, DNS, or
system time. It inspects the current chrony state, looks for local GNSS/PPS/PTP
reference-clock evidence, discovers NTP servers explicitly advertised by the
host network (DHCP/networkd leases plus the default gateway), and measures a
small reviewed list of Icelandic candidate NTP servers.

It does NOT sweep the hosting provider subnet. Probing arbitrary neighbouring
addresses requires separate authorization from the network operator.
"""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import ipaddress
import json
import os
import re
import socket
import statistics
import subprocess
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from ntp_rtt_probe import load_sources, probe_source


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CANDIDATES = (
    REPO_ROOT / "modules" / "time-authority" / "config" / "iceland-candidate-sources.json"
)
SCHEMA_VERSION = 1
GPS_REFID_HINTS = {
    "GPS",
    "GNSS",
    "PPS",
    "ATOM",
    "PTP",
    "GAL",
    "GLO",
    "GLON",
}
LEASE_GLOBS = (
    "/run/systemd/netif/leases/*",
    "/var/lib/NetworkManager/*.lease",
    "/var/lib/dhcp/dhclient*.leases",
)
DEVICE_GLOBS = (
    "/dev/pps*",
    "/dev/ptp*",
    "/dev/gps*",
    "/dev/ttyACM*",
    "/dev/ttyUSB*",
)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def run_command(argv: Sequence[str], timeout: float = 5.0) -> Dict[str, Any]:
    try:
        completed = subprocess.run(
            list(argv),
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "argv": list(argv),
            "available": True,
            "returncode": completed.returncode,
            "stdout": completed.stdout.strip(),
            "stderr": completed.stderr.strip(),
        }
    except FileNotFoundError:
        return {
            "argv": list(argv),
            "available": False,
            "returncode": None,
            "stdout": "",
            "stderr": "command_not_found",
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "argv": list(argv),
            "available": True,
            "returncode": None,
            "stdout": (exc.stdout or "").strip() if isinstance(exc.stdout, str) else "",
            "stderr": "timeout",
        }


def safe_read(path: Path, max_bytes: int = 256_000) -> str:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            return handle.read(max_bytes)
    except (OSError, UnicodeError):
        return ""


def parse_selected_chrony_source(text: str) -> Optional[Dict[str, str]]:
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith("^*") and not line.startswith("#*"):
            continue
        fields = line.split()
        if len(fields) >= 2:
            return {
                "type": "refclock" if line.startswith("#*") else "network",
                "source": fields[1],
                "raw": line,
            }
    return None


def inspect_chrony() -> Dict[str, Any]:
    tracking = run_command(["chronyc", "-n", "tracking"])
    sources = run_command(["chronyc", "-n", "sources", "-v"])
    sourcestats = run_command(["chronyc", "-n", "sourcestats", "-v"])
    activity = run_command(["chronyc", "activity"])
    return {
        "tracking": tracking,
        "sources": sources,
        "sourcestats": sourcestats,
        "activity": activity,
        "selected_source": parse_selected_chrony_source(sources.get("stdout", "")),
    }


def inspect_reference_clock_devices() -> Dict[str, Any]:
    devices: List[str] = []
    for pattern in DEVICE_GLOBS:
        devices.extend(glob.glob(pattern))
    devices = sorted(set(devices))

    gpsd = run_command(["systemctl", "is-active", "gpsd.service"], timeout=3.0)
    gpsd_socket = run_command(["systemctl", "is-active", "gpsd.socket"], timeout=3.0)

    return {
        "devices": devices,
        "gpsd_service": gpsd,
        "gpsd_socket": gpsd_socket,
        "direct_reference_evidence": bool(devices)
        or gpsd.get("stdout") == "active"
        or gpsd_socket.get("stdout") == "active",
    }


def token_to_ip(token: str) -> Optional[str]:
    candidate = token.strip().strip(";,\"'")
    candidate = candidate.strip("[]")
    try:
        address = ipaddress.ip_address(candidate)
    except ValueError:
        return None
    if address.version != 4:
        return None
    return str(address)


def parse_advertised_ntp_servers(text: str) -> Set[str]:
    servers: Set[str] = set()
    patterns = (
        re.compile(r"^(?:NTP|NTP_SERVERS)=(.+)$", re.IGNORECASE),
        re.compile(r"option\s+ntp-servers\s+(.+?);", re.IGNORECASE),
    )
    for raw_line in text.splitlines():
        line = raw_line.strip()
        for pattern in patterns:
            match = pattern.search(line)
            if not match:
                continue
            payload = match.group(1).replace(",", " ")
            for token in payload.split():
                ip = token_to_ip(token)
                if ip:
                    servers.add(ip)
    return servers


def discover_lease_ntp_servers() -> List[Dict[str, str]]:
    found: Dict[str, Set[str]] = {}
    for pattern in LEASE_GLOBS:
        for raw_path in glob.glob(pattern):
            path = Path(raw_path)
            text = safe_read(path)
            for server in parse_advertised_ntp_servers(text):
                found.setdefault(server, set()).add(str(path))

    return [
        {
            "address": server,
            "kind": "network-advertised-ntp",
            "evidence": ",".join(sorted(paths)),
        }
        for server, paths in sorted(found.items())
    ]


def discover_default_gateways() -> List[Dict[str, str]]:
    result = run_command(["ip", "-j", "-4", "route", "show", "default"])
    if result.get("returncode") != 0 or not result.get("stdout"):
        return []
    try:
        routes = json.loads(result["stdout"])
    except json.JSONDecodeError:
        return []

    gateways: List[Dict[str, str]] = []
    seen: Set[str] = set()
    for route in routes:
        gateway = str(route.get("gateway", "")).strip()
        if not gateway or gateway in seen:
            continue
        try:
            address = ipaddress.ip_address(gateway)
        except ValueError:
            continue
        if address.version != 4:
            continue
        seen.add(gateway)
        gateways.append(
            {
                "address": gateway,
                "kind": "default-gateway-ntp-check",
                "evidence": str(route.get("dev", "")),
            }
        )
    return gateways


def collect_local_candidates() -> List[Dict[str, str]]:
    combined: Dict[str, Dict[str, str]] = {}
    for item in discover_lease_ntp_servers() + discover_default_gateways():
        address = item["address"]
        existing = combined.get(address)
        if existing:
            existing["kind"] = existing["kind"] + "+" + item["kind"]
            if item.get("evidence"):
                existing["evidence"] = ",".join(
                    filter(None, [existing.get("evidence", ""), item["evidence"]])
                )
        else:
            combined[address] = dict(item)
    return list(combined.values())


def summarize_samples(source: Dict[str, Any], records: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    reachable = [record for record in records if record.get("reachable")]
    strata = [int(record["stratum"]) for record in reachable if record.get("stratum") is not None]
    refids = sorted({str(record.get("refid") or "") for record in reachable if record.get("refid")})
    rtts = [float(record["rtt_ms"]) for record in reachable if record.get("rtt_ms") is not None]
    offsets = [
        float(record["clock_offset_ms"])
        for record in reachable
        if record.get("clock_offset_ms") is not None
    ]
    dispersions = [
        float(record["root_dispersion_ms"])
        for record in reachable
        if record.get("root_dispersion_ms") is not None
    ]

    dominant_stratum = None
    if strata:
        dominant_stratum = statistics.mode(strata)

    evidence = "none"
    reason = "No GNSS/GPS evidence from the bounded probe."
    documented_reference = str(source.get("reference_type_documented", ""))
    if reachable and dominant_stratum == 1 and documented_reference:
        evidence = "documented-reference-plus-live-stratum1"
        reason = f"Provider documentation identifies {documented_reference}; live NTP replies report stratum 1."
    elif reachable and dominant_stratum == 1 and any(refid.upper() in GPS_REFID_HINTS for refid in refids):
        evidence = "packet-refid-hint"
        reason = "Live stratum-1 reply contains a reference ID commonly associated with a reference clock; this is a hint, not hardware proof."

    return {
        "samples_requested": len(records),
        "samples_reachable": len(reachable),
        "reachable": bool(reachable),
        "resolved_addresses": sorted(
            {str(record.get("resolved_address")) for record in reachable if record.get("resolved_address")}
        ),
        "dominant_stratum": dominant_stratum,
        "refids": refids,
        "median_rtt_ms": round(statistics.median(rtts), 3) if rtts else None,
        "min_rtt_ms": round(min(rtts), 3) if rtts else None,
        "median_clock_offset_ms": round(statistics.median(offsets), 3) if offsets else None,
        "max_abs_clock_offset_ms": round(max(abs(value) for value in offsets), 3) if offsets else None,
        "median_root_dispersion_ms": round(statistics.median(dispersions), 3) if dispersions else None,
        "expectation_passes": sum(1 for record in reachable if record.get("expectation_ok")),
        "gnss_evidence": {
            "classification": evidence,
            "reason": reason,
        },
        "errors": [str(record.get("error")) for record in records if record.get("error")],
    }


def probe_many(
    source: Dict[str, Any],
    *,
    samples: int,
    timeout: float,
    observer_host: str,
) -> Dict[str, Any]:
    records = [
        probe_source(
            source,
            observer_id="edge1-time-source-discovery",
            observer_host=observer_host,
            timeout=timeout,
        )
        for _ in range(samples)
    ]
    return {
        "source": source,
        "summary": summarize_samples(source, records),
        "samples": records,
    }


def build_local_source(item: Dict[str, str]) -> Dict[str, Any]:
    address = item["address"]
    return {
        "source_id": f"local-{address.replace('.', '-')}",
        "server_name": address,
        "provider": "local-network-candidate",
        "region": "Edge1 directly configured network path",
        "expected_stratum_min": 1,
        "expected_stratum_max": 15,
        "expected_refids": [],
        "candidate_only": True,
        "discovery_kind": item.get("kind", ""),
        "discovery_evidence": item.get("evidence", ""),
    }


def build_report(args: argparse.Namespace) -> Dict[str, Any]:
    observer_host = socket.getfqdn()
    chrony = inspect_chrony()
    reference_devices = inspect_reference_clock_devices()

    candidate_sources = load_sources(args.candidates)
    candidate_results = [
        probe_many(
            source,
            samples=args.samples,
            timeout=args.timeout,
            observer_host=observer_host,
        )
        for source in candidate_sources
    ]

    local_discovery = collect_local_candidates()
    local_results = [
        probe_many(
            build_local_source(item),
            samples=args.local_samples,
            timeout=args.timeout,
            observer_host=observer_host,
        )
        for item in local_discovery
    ]

    notes: List[str] = []
    if not local_discovery:
        notes.append("No NTP servers were found in readable DHCP/networkd lease data and no default gateway could be probed as a candidate.")
    notes.append("The probe intentionally does not sweep neighbouring VPS/public subnet addresses.")
    notes.append("A single good probe is candidate evidence only; production source changes should be based on repeated measurements and chrony selection statistics.")

    return {
        "schema_version": SCHEMA_VERSION,
        "observed_at_utc": utc_now(),
        "observer_host": observer_host,
        "mode": "read-only",
        "chrony": chrony,
        "reference_clock_inspection": reference_devices,
        "iceland_candidates": candidate_results,
        "local_network_discovery": {
            "candidates": local_discovery,
            "probe_results": local_results,
        },
        "notes": notes,
    }


def print_human_summary(report: Dict[str, Any]) -> None:
    print("=== EDGE1 TIME SOURCE DISCOVERY ===")
    print(f"Observed: {report['observed_at_utc']}")
    selected = report.get("chrony", {}).get("selected_source")
    if selected:
        print(f"Current selected chrony source: {selected.get('source')} ({selected.get('type')})")
    else:
        print("Current selected chrony source: not determined")

    refs = report.get("reference_clock_inspection", {})
    devices = refs.get("devices", [])
    print(f"Direct PPS/PTP/GPS-like devices: {', '.join(devices) if devices else 'none detected'}")

    print("\nIceland candidates:")
    for candidate in report.get("iceland_candidates", []):
        source = candidate["source"]
        summary = candidate["summary"]
        if summary.get("reachable"):
            print(
                f"  {source['server_name']}: stratum={summary.get('dominant_stratum')} "
                f"median_rtt={summary.get('median_rtt_ms')}ms "
                f"median_offset={summary.get('median_clock_offset_ms')}ms "
                f"refid={','.join(summary.get('refids') or []) or '-'} "
                f"gnss={summary.get('gnss_evidence', {}).get('classification')}"
            )
        else:
            print(f"  {source['server_name']}: unreachable ({'; '.join(summary.get('errors') or [])})")

    local = report.get("local_network_discovery", {})
    print("\nNetwork-advertised/default-gateway candidates:")
    if not local.get("probe_results"):
        print("  none")
    for candidate in local.get("probe_results", []):
        source = candidate["source"]
        summary = candidate["summary"]
        print(
            f"  {source['server_name']}: reachable={summary.get('reachable')} "
            f"stratum={summary.get('dominant_stratum')} "
            f"median_rtt={summary.get('median_rtt_ms')}ms "
            f"kind={source.get('discovery_kind')}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--local-samples", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=1.5)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--pretty", action="store_true", help="Print complete JSON after the human summary")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not 1 <= args.samples <= 20:
        raise SystemExit("--samples must be between 1 and 20")
    if not 1 <= args.local_samples <= 10:
        raise SystemExit("--local-samples must be between 1 and 10")
    if not 0.25 <= args.timeout <= 10.0:
        raise SystemExit("--timeout must be between 0.25 and 10 seconds")
    if not args.candidates.is_file():
        raise SystemExit(f"candidate source file not found: {args.candidates}")

    report = build_report(args)
    print_human_summary(report)

    payload = json.dumps(report, indent=2, sort_keys=True)
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(payload + "\n", encoding="utf-8")
        print(f"\nJSON evidence: {args.json_output}")
    if args.pretty:
        print("\n=== JSON ===")
        print(payload)

    reachable = any(
        candidate.get("summary", {}).get("reachable")
        for candidate in report.get("iceland_candidates", [])
    )
    return 0 if reachable else 2


if __name__ == "__main__":
    raise SystemExit(main())
