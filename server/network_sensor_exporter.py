#!/usr/bin/env python3
"""Aggregate Edge1 passive sensor records into restricted and dashboard snapshots."""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import ipaddress
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Iterable

CONTRACT = "wwcx.edge1-network-sensor.v1"
DEFAULT_INTERNAL = ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "127.0.0.0/8", "::1/128", "fc00::/7")
EVENT_LIMIT = 1000
TOP_LIMIT = 50


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def read_json_lines(path: Path, limit: int) -> list[dict[str, Any]]:
    rows: collections.deque[dict[str, Any]] = collections.deque(maxlen=limit)
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                rows.append(value)
    return list(rows)


def iter_zeek_json(log_dir: Path, names: Iterable[str], per_file: int = 500) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for name in names:
        for path in sorted(log_dir.glob(f"{name}*.log"))[-4:]:
            for row in read_json_lines(path, per_file):
                result.append({"zeek_log": name, **row})
    return result[-EVENT_LIMIT:]


def safe_ip(value: Any) -> ipaddress._BaseAddress | None:
    try:
        return ipaddress.ip_address(str(value))
    except ValueError:
        return None


def parse_networks(values: Iterable[str]) -> tuple[ipaddress._BaseNetwork, ...]:
    return tuple(ipaddress.ip_network(item, strict=False) for item in values)


def is_internal(value: Any, networks: tuple[ipaddress._BaseNetwork, ...]) -> bool:
    address = safe_ip(value)
    return bool(address and any(address.version == network.version and address in network for network in networks))


def add(counter: collections.Counter[str], value: Any) -> None:
    if value is not None:
        text = str(value).strip()
        if text:
            counter[text] += 1


def top(counter: collections.Counter[str], limit: int = TOP_LIMIT) -> list[dict[str, Any]]:
    return [{"value": value, "count": count} for value, count in counter.most_common(limit)]


def directory_usage(path: Path) -> dict[str, Any]:
    files = 0
    bytes_total = 0
    newest_mtime = 0.0
    if path.is_dir():
        for item in path.rglob("*"):
            try:
                if item.is_file():
                    stat_result = item.stat()
                    files += 1
                    bytes_total += stat_result.st_size
                    newest_mtime = max(newest_mtime, stat_result.st_mtime)
            except OSError:
                continue
    return {
        "path": str(path),
        "files": files,
        "bytes": bytes_total,
        "newest_mtime_utc": dt.datetime.fromtimestamp(newest_mtime, dt.timezone.utc).isoformat() if newest_mtime else None,
    }


def build_snapshot(
    eve_path: Path,
    zeek_dir: Path,
    pcap_dir: Path,
    extracted_dir: Path,
    interface: str,
    internal_networks: tuple[ipaddress._BaseNetwork, ...],
    now: dt.datetime | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    now = now or utc_now()
    events = read_json_lines(eve_path, EVENT_LIMIT)
    zeek_events = iter_zeek_json(zeek_dir, ("conn", "dns", "http", "ssl", "x509", "ssh", "files", "smb_files", "rdp"))

    event_types: collections.Counter[str] = collections.Counter()
    protocols: collections.Counter[str] = collections.Counter()
    app_protocols: collections.Counter[str] = collections.Counter()
    internal_sources: collections.Counter[str] = collections.Counter()
    external_destinations: collections.Counter[str] = collections.Counter()
    destination_ports: collections.Counter[str] = collections.Counter()
    dns_queries: collections.Counter[str] = collections.Counter()
    tls_sni: collections.Counter[str] = collections.Counter()
    http_hosts: collections.Counter[str] = collections.Counter()
    http_methods: collections.Counter[str] = collections.Counter()
    alerts: collections.Counter[str] = collections.Counter()
    flow_bytes_to_external = 0
    flow_bytes_from_external = 0

    for event in events:
        event_type = str(event.get("event_type", "unknown"))
        event_types[event_type] += 1
        add(protocols, event.get("proto"))
        add(app_protocols, event.get("app_proto"))
        src = event.get("src_ip")
        dst = event.get("dest_ip")
        if is_internal(src, internal_networks):
            add(internal_sources, src)
        if dst and not is_internal(dst, internal_networks):
            add(external_destinations, dst)
        add(destination_ports, event.get("dest_port"))

        dns = event.get("dns")
        if isinstance(dns, dict):
            add(dns_queries, dns.get("rrname") or dns.get("query"))

        tls = event.get("tls")
        if isinstance(tls, dict):
            add(tls_sni, tls.get("sni"))

        http = event.get("http")
        if isinstance(http, dict):
            add(http_hosts, http.get("hostname") or http.get("host"))
            add(http_methods, http.get("http_method"))

        alert = event.get("alert")
        if isinstance(alert, dict):
            add(alerts, alert.get("signature"))

        flow = event.get("flow")
        if isinstance(flow, dict):
            to_server = int(flow.get("bytes_toserver", 0) or 0)
            to_client = int(flow.get("bytes_toclient", 0) or 0)
            if is_internal(src, internal_networks) and dst and not is_internal(dst, internal_networks):
                flow_bytes_to_external += to_server
                flow_bytes_from_external += to_client

    for event in zeek_events:
        src = event.get("id.orig_h")
        dst = event.get("id.resp_h")
        if is_internal(src, internal_networks):
            add(internal_sources, src)
        if dst and not is_internal(dst, internal_networks):
            add(external_destinations, dst)
        add(destination_ports, event.get("id.resp_p"))
        add(protocols, event.get("proto"))
        add(app_protocols, event.get("service"))
        add(dns_queries, event.get("query"))
        add(http_hosts, event.get("host"))
        add(http_methods, event.get("method"))
        add(tls_sni, event.get("server_name"))

    pcap = directory_usage(pcap_dir)
    extracted = directory_usage(extracted_dir)
    disk = shutil.disk_usage(pcap_dir if pcap_dir.exists() else pcap_dir.parent)

    summary = {
        "contract": CONTRACT,
        "generated_at": now.isoformat(),
        "profile": "owner-full",
        "mode": "passive_mirror",
        "interface": interface,
        "capture": {
            "full_packet_capture": True,
            "snap_length": 0,
            "packet_payloads_retained": True,
            "encrypted_payloads_decrypted": False,
            "suricata_eve_available": eve_path.is_file(),
            "zeek_logs_available": zeek_dir.is_dir() and any(zeek_dir.glob("*.log")),
        },
        "totals": {
            "suricata_events_sampled": len(events),
            "zeek_events_sampled": len(zeek_events),
            "flow_bytes_to_external": flow_bytes_to_external,
            "flow_bytes_from_external": flow_bytes_from_external,
        },
        "top": {
            "event_types": top(event_types),
            "protocols": top(protocols),
            "application_protocols": top(app_protocols),
            "internal_sources": top(internal_sources),
            "external_destinations": top(external_destinations),
            "destination_ports": top(destination_ports),
            "dns_queries": top(dns_queries),
            "tls_server_names": top(tls_sni),
            "http_hosts": top(http_hosts),
            "http_methods": top(http_methods),
            "alerts": top(alerts),
        },
        "storage": {
            "pcap": pcap,
            "extracted_files": extracted,
            "filesystem_free_bytes": disk.free,
            "filesystem_total_bytes": disk.total,
        },
    }

    restricted = {
        **summary,
        "visibility": "restricted-owner-full",
        "internal_networks": [str(network) for network in internal_networks],
        "recent_suricata_events": events,
        "recent_zeek_events": zeek_events,
    }

    public = {
        **summary,
        "visibility": "dashboard-summary",
        "top": {
            "event_types": summary["top"]["event_types"],
            "protocols": summary["top"]["protocols"],
            "application_protocols": summary["top"]["application_protocols"],
            "destination_ports": summary["top"]["destination_ports"],
            "alerts": summary["top"]["alerts"],
        },
    }
    return restricted, public


def atomic_write(path: Path, value: dict[str, Any], mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--eve", type=Path, default=Path("/var/log/wwcx-network-sensor/suricata/eve.json"))
    parser.add_argument("--zeek-dir", type=Path, default=Path("/var/log/wwcx-network-sensor/zeek"))
    parser.add_argument("--pcap-dir", type=Path, default=Path("/var/lib/wwcx-network-sensor/pcap"))
    parser.add_argument("--extracted-dir", type=Path, default=Path("/var/lib/wwcx-network-sensor/extracted"))
    parser.add_argument("--restricted-output", type=Path, default=Path("/var/lib/wwcx-network-sensor/restricted/latest.json"))
    parser.add_argument("--public-output", type=Path, default=Path("/var/www/edge1-status/network-sensor/data/network-sensor.json"))
    parser.add_argument("--interface", default=os.environ.get("SENSOR_INTERFACE", "unconfigured"))
    parser.add_argument("--internal-network", action="append", default=[])
    args = parser.parse_args()
    networks = parse_networks(args.internal_network or DEFAULT_INTERNAL)
    restricted, public = build_snapshot(args.eve, args.zeek_dir, args.pcap_dir, args.extracted_dir, args.interface, networks)
    atomic_write(args.restricted_output, restricted, 0o600)
    atomic_write(args.public_output, public, 0o644)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
