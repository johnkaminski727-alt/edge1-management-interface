#!/usr/bin/env python3
"""Bounded LAN observation for Project Big Bird cameras.

This tool does not scan address ranges. By default it only reads the local kernel
neighbor table. Optional TCP probing is limited to a private/link-local address that
was already observed in that table and to a fixed camera-relevant port allowlist.
"""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_EVIDENCE_DIR = Path(os.environ.get("BIGBIRD_CAMERA_DISCOVERY_EVIDENCE_DIR", "/var/lib/bigbird-camera/discovery"))
PROBE_PORTS = (80, 443, 554)
CONNECT_TIMEOUT_SECONDS = 1.5


class DiscoveryError(RuntimeError):
    pass


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _private_lan_ip(value: str) -> ipaddress._BaseAddress:
    try:
        ip = ipaddress.ip_address(value)
    except ValueError as exc:
        raise DiscoveryError("candidate IP is invalid") from exc
    if ip.is_unspecified or ip.is_multicast or ip.is_loopback or ip.is_global:
        raise DiscoveryError("candidate IP must be a non-loopback private or link-local address")
    if not (ip.is_private or ip.is_link_local):
        raise DiscoveryError("candidate IP must be private or link-local")
    return ip


def read_neighbors() -> list[dict[str, Any]]:
    try:
        result = subprocess.run(
            ["ip", "-j", "neigh", "show"], text=True, capture_output=True,
            timeout=5, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DiscoveryError(f"neighbor observation failed: {exc}") from exc
    if result.returncode != 0:
        raise DiscoveryError("neighbor observation failed")
    try:
        payload = json.loads(result.stdout or "[]")
    except json.JSONDecodeError as exc:
        raise DiscoveryError("neighbor observation returned invalid JSON") from exc
    if not isinstance(payload, list):
        raise DiscoveryError("neighbor observation returned unexpected data")
    return normalize_neighbors(payload)


def normalize_neighbors(payload: list[dict[str, Any]]) -> list[dict[str, Any]]:
    observed: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        dst = str(item.get("dst", "")).strip()
        if not dst:
            continue
        try:
            ip = _private_lan_ip(dst)
        except DiscoveryError:
            continue
        record: dict[str, Any] = {
            "ip": str(ip),
            "dev": str(item.get("dev", "")).strip() or None,
            "state": [str(x) for x in item.get("state", [])] if isinstance(item.get("state"), list) else [],
        }
        lladdr = str(item.get("lladdr", "")).strip().lower()
        if lladdr:
            record["mac"] = lladdr
        observed.append(record)
    return sorted(observed, key=lambda r: (ipaddress.ip_address(r["ip"]).version, int(ipaddress.ip_address(r["ip"]))))


def _probe_tcp(ip: str, port: int) -> bool:
    family = socket.AF_INET6 if ipaddress.ip_address(ip).version == 6 else socket.AF_INET
    with socket.socket(family, socket.SOCK_STREAM) as sock:
        sock.settimeout(CONNECT_TIMEOUT_SECONDS)
        try:
            return sock.connect_ex((ip, port)) == 0
        except OSError:
            return False


def probe_observed_candidate(ip: str, neighbors: list[dict[str, Any]]) -> dict[str, Any]:
    candidate = str(_private_lan_ip(ip))
    observed_ips = {row["ip"] for row in neighbors}
    if candidate not in observed_ips:
        raise DiscoveryError("active probe refused: candidate was not observed in the local neighbor table")
    ports = [{"port": port, "tcp_open": _probe_tcp(candidate, port)} for port in PROBE_PORTS]
    return {"ip": candidate, "ports": ports}


def _private_evidence_record(neighbors: list[dict[str, Any]], probe: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "contract": "wwcx.bigbird-camera-discovery.v1",
        "observed_at": utcnow(),
        "source": "kernel_neighbor_table",
        "neighbors": neighbors,
        "probe": probe,
        "limits": {
            "address_range_scan": False,
            "internet_scan": False,
            "probe_ports": list(PROBE_PORTS),
            "probe_requires_observed_candidate": True,
        },
    }


def write_evidence(record: dict[str, Any], evidence_dir: Path = DEFAULT_EVIDENCE_DIR) -> Path:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(evidence_dir, 0o700)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = evidence_dir / f"camera-discovery-{stamp}.json"
    temp = target.with_suffix(".json.tmp")
    temp.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(temp, 0o600)
    temp.replace(target)
    return target


def sanitized_summary(record: dict[str, Any], evidence: Path) -> dict[str, Any]:
    digest = hashlib.sha256(evidence.read_bytes()).hexdigest()
    probe = record.get("probe")
    open_ports = [] if not probe else [x["port"] for x in probe["ports"] if x["tcp_open"]]
    return {
        "status": "observation_complete",
        "neighbor_count": len(record["neighbors"]),
        "candidate_probed": probe is not None,
        "open_candidate_ports": open_ports,
        "evidence_path": str(evidence),
        "evidence_sha256": digest,
        "private_identifiers_in_stdout": False,
    }


def run(candidate_ip: str | None = None, evidence_dir: Path = DEFAULT_EVIDENCE_DIR) -> dict[str, Any]:
    neighbors = read_neighbors()
    probe = probe_observed_candidate(candidate_ip, neighbors) if candidate_ip else None
    record = _private_evidence_record(neighbors, probe)
    evidence = write_evidence(record, evidence_dir)
    return sanitized_summary(record, evidence)


def main() -> None:
    parser = argparse.ArgumentParser(description="Observe bounded owner-LAN camera candidates")
    parser.add_argument("--probe-observed", metavar="IP", help="probe fixed camera ports on one already-observed private candidate")
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    args = parser.parse_args()
    try:
        print(json.dumps(run(args.probe_observed, args.evidence_dir), indent=2, sort_keys=True))
    except DiscoveryError as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, indent=2, sort_keys=True))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
