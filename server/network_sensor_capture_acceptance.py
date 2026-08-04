#!/usr/bin/env python3
"""Validate that Suricata observes traffic seen on its capture interface."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import time
from pathlib import Path
from typing import Any

CONTRACT = "wwcx.network-sensor-capture-acceptance.v1"
TAIL_BYTES = 4 * 1024 * 1024


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def parse_timestamp(value: str) -> dt.datetime:
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    if len(text) >= 5 and text[-5] in "+-" and text[-3] != ":":
        text = text[:-2] + ":" + text[-2:]
    parsed = dt.datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def tail_lines(path: Path, max_bytes: int = TAIL_BYTES) -> list[str]:
    if not path.is_file():
        return []
    with path.open("rb") as handle:
        size = path.stat().st_size
        start = max(0, size - max_bytes)
        handle.seek(start)
        if start:
            handle.readline()
        data = handle.read()
    return data.decode("utf-8", errors="replace").splitlines()


def latest_current_run_stats(path: Path, started_at: dt.datetime) -> dict[str, Any] | None:
    latest: dict[str, Any] | None = None
    for line in tail_lines(path):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict) or row.get("event_type") != "stats":
            continue
        try:
            timestamp = parse_timestamp(str(row.get("timestamp", "")))
        except (TypeError, ValueError):
            continue
        if timestamp < started_at:
            continue
        stats = row.get("stats")
        if not isinstance(stats, dict):
            continue
        capture = stats.get("capture") if isinstance(stats.get("capture"), dict) else {}
        decoder = stats.get("decoder") if isinstance(stats.get("decoder"), dict) else {}
        candidate = {
            "timestamp": timestamp.isoformat(),
            "kernel_packets": int(capture.get("kernel_packets", 0) or 0),
            "kernel_drops": int(capture.get("kernel_drops", 0) or 0),
            "decoder_packets": int(decoder.get("pkts", 0) or 0),
            "decoder_bytes": int(decoder.get("bytes", 0) or 0),
        }
        if latest is None or candidate["timestamp"] >= latest["timestamp"]:
            latest = candidate
    return latest


def interface_packet_count(interface: str, sys_class_net: Path = Path("/sys/class/net")) -> int:
    if not interface or "/" in interface or interface in {".", ".."}:
        raise ValueError("invalid interface name")
    base = sys_class_net / interface / "statistics"
    rx_packets = int((base / "rx_packets").read_text(encoding="ascii").strip())
    tx_packets = int((base / "tx_packets").read_text(encoding="ascii").strip())
    return rx_packets + tx_packets


def packet_total(stats: dict[str, Any] | None) -> int:
    if not stats:
        return 0
    return max(int(stats.get("kernel_packets", 0)), int(stats.get("decoder_packets", 0)))


def evaluate(interface_before: int, interface_after: int, stats: dict[str, Any] | None) -> dict[str, Any]:
    stats = stats or {
        "timestamp": None,
        "kernel_packets": 0,
        "kernel_drops": 0,
        "decoder_packets": 0,
        "decoder_bytes": 0,
    }
    interface_delta = max(0, interface_after - interface_before)
    suricata_packets = packet_total(stats)
    if suricata_packets > 0:
        result = "pass"
    elif interface_delta > 0:
        result = "fail-active-interface-suricata-zero"
    else:
        result = "inconclusive-no-interface-traffic"
    return {
        "result": result,
        "capture_validated": result == "pass",
        "traffic_observed": interface_delta > 0 or suricata_packets > 0,
        "interface_packets_before": interface_before,
        "interface_packets_after": interface_after,
        "interface_packets_delta": interface_delta,
        "suricata": stats,
    }


def wait_for_stats(eve: Path, started_at: dt.datetime, seconds: float, poll_seconds: float) -> dict[str, Any] | None:
    deadline = time.monotonic() + max(0.0, seconds)
    latest = latest_current_run_stats(eve, started_at)
    while latest is None:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(max(0.1, poll_seconds), remaining))
        latest = latest_current_run_stats(eve, started_at)
    return latest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--interface", required=True)
    parser.add_argument("--eve", type=Path, default=Path("/var/log/wwcx-network-sensor/suricata/eve.json"))
    parser.add_argument("--started-at", required=True)
    parser.add_argument("--startup-wait-seconds", type=float, default=75.0)
    parser.add_argument("--observation-seconds", type=float, default=30.0)
    parser.add_argument("--poll-seconds", type=float, default=3.0)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--sys-class-net", type=Path, default=Path("/sys/class/net"))
    args = parser.parse_args()

    started_at = parse_timestamp(args.started_at)
    startup_interface_before = interface_packet_count(args.interface, args.sys_class_net)
    latest = wait_for_stats(args.eve, started_at, args.startup_wait_seconds, args.poll_seconds)

    if latest is None:
        interface_before = startup_interface_before
        phase = "startup"
    else:
        interface_before = interface_packet_count(args.interface, args.sys_class_net)
        phase = "observation"
        deadline = time.monotonic() + max(0.0, args.observation_seconds)
        while packet_total(latest) <= 0:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(max(0.1, args.poll_seconds), remaining))
            latest = latest_current_run_stats(args.eve, started_at) or latest

    interface_after = interface_packet_count(args.interface, args.sys_class_net)
    result = {
        "contract": CONTRACT,
        "interface": args.interface,
        "started_at": started_at.isoformat(),
        "checked_at": utc_now().isoformat(),
        "startup_wait_seconds": args.startup_wait_seconds,
        "observation_seconds": args.observation_seconds,
        "phase_completed": phase,
        "current_run_stats_observed": latest is not None,
        **evaluate(interface_before, interface_after, latest),
    }
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 1 if result["result"] == "fail-active-interface-suricata-zero" else 0


if __name__ == "__main__":
    raise SystemExit(main())
