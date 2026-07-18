#!/usr/bin/env python3
"""Collect bounded, read-only NTP RTT and clock-offset observations."""

import argparse
import datetime as dt
import fcntl
import json
import os
import socket
import struct
import time
from pathlib import Path
from typing import Any, Optional


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCES = REPO_ROOT / "modules" / "time-authority" / "config" / "sources.json"
NTP_UNIX_EPOCH_DELTA = 2_208_988_800
SCHEMA_VERSION = 1


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def encode_ntp_timestamp(unix_seconds: float) -> bytes:
    whole = int(unix_seconds) + NTP_UNIX_EPOCH_DELTA
    fraction = int((unix_seconds - int(unix_seconds)) * (1 << 32))
    return struct.pack("!II", whole, fraction)


def decode_ntp_timestamp(raw: bytes) -> float:
    whole, fraction = struct.unpack("!II", raw)
    return (whole - NTP_UNIX_EPOCH_DELTA) + fraction / float(1 << 32)


def decode_fixed_16_16(raw: bytes, *, signed: bool) -> float:
    value = int.from_bytes(raw, "big", signed=signed)
    return value / 65536.0


def decode_refid(raw: bytes, stratum: int) -> str:
    if stratum == 1:
        return raw.decode("ascii", "replace").rstrip("\0").strip()
    return socket.inet_ntoa(raw)


def source_expectation_ok(source: dict[str, Any], stratum: int, refid: str) -> bool:
    expected = source.get("expected_stratum")
    if expected is not None and stratum != int(expected):
        return False
    minimum = source.get("expected_stratum_min")
    maximum = source.get("expected_stratum_max")
    if minimum is not None and stratum < int(minimum):
        return False
    if maximum is not None and stratum > int(maximum):
        return False
    refids = [str(item) for item in source.get("expected_refids", [])]
    return not refids or refid in refids


def probe_source(
    source: dict[str, Any],
    *,
    observer_id: str,
    observer_host: str,
    timeout: float,
) -> dict[str, Any]:
    observed_at = utc_now()
    host = str(source["server_name"])
    port = int(source.get("port", 123))
    record: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "observed_at_utc": observed_at,
        "observer_id": observer_id,
        "observer_host": observer_host,
        "source_id": str(source["source_id"]),
        "server_name": host,
        "provider": str(source.get("provider", "")),
        "region": str(source.get("region", "")),
        "reachable": False,
        "resolved_address": None,
        "stratum": None,
        "refid": None,
        "rtt_ms": None,
        "network_delay_ms": None,
        "clock_offset_ms": None,
        "root_delay_ms": None,
        "root_dispersion_ms": None,
        "leap_indicator": None,
        "ntp_version": None,
        "response_mode": None,
        "expectation_ok": False,
        "error": None,
    }

    sock = None  # type: Optional[socket.socket]
    try:
        address = socket.gethostbyname(host)
        record["resolved_address"] = address
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)

        request = bytearray(48)
        request[0] = 0x23  # LI=0, VN=4, mode=3 (client)
        wall_started = time.time()
        origin = encode_ntp_timestamp(wall_started)
        request[40:48] = origin
        monotonic_started = time.monotonic()
        sock.sendto(request, (address, port))
        response, peer = sock.recvfrom(512)
        monotonic_finished = time.monotonic()
        wall_finished = time.time()

        if len(response) < 48:
            raise ValueError(f"short_response_{len(response)}")
        if response[24:32] != origin:
            raise ValueError("origin_timestamp_mismatch")

        leap_indicator = response[0] >> 6
        version = (response[0] >> 3) & 0x07
        mode = response[0] & 0x07
        stratum = int(response[1])
        if mode != 4:
            raise ValueError(f"unexpected_mode_{mode}")
        if version not in (3, 4):
            raise ValueError(f"unexpected_version_{version}")
        if stratum == 0 or stratum >= 16 or leap_indicator == 3:
            raise ValueError(f"unsynchronized_stratum_{stratum}")

        server_received = decode_ntp_timestamp(response[32:40])
        server_transmitted = decode_ntp_timestamp(response[40:48])
        network_delay = (wall_finished - wall_started) - (server_transmitted - server_received)
        clock_offset = ((server_received - wall_started) + (server_transmitted - wall_finished)) / 2.0
        refid = decode_refid(response[12:16], stratum)

        record.update(
            {
                "reachable": True,
                "resolved_address": peer[0],
                "stratum": stratum,
                "refid": refid,
                "rtt_ms": round((monotonic_finished - monotonic_started) * 1000.0, 3),
                "network_delay_ms": round(network_delay * 1000.0, 3),
                "clock_offset_ms": round(clock_offset * 1000.0, 3),
                "root_delay_ms": round(decode_fixed_16_16(response[4:8], signed=True) * 1000.0, 3),
                "root_dispersion_ms": round(decode_fixed_16_16(response[8:12], signed=False) * 1000.0, 3),
                "leap_indicator": leap_indicator,
                "ntp_version": version,
                "response_mode": mode,
                "expectation_ok": source_expectation_ok(source, stratum, refid),
            }
        )
    except (OSError, ValueError, struct.error) as exc:
        record["error"] = exc.__class__.__name__ + ":" + str(exc)[:160]
    finally:
        if sock is not None:
            sock.close()
    return record


def load_sources(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    sources = payload.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("source configuration must contain a non-empty sources list")
    required = {"source_id", "server_name"}
    for item in sources:
        if not isinstance(item, dict) or not required.issubset(item):
            raise ValueError("each source requires source_id and server_name")
    return sources


def append_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
    payload = "".join(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n" for record in records)
    with path.open("a", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observer-id", required=True)
    parser.add_argument("--observer-host", default=socket.getfqdn())
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--timeout", type=float, default=4.0)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not 0.25 <= args.timeout <= 30:
        raise SystemExit("--timeout must be between 0.25 and 30 seconds")
    sources = load_sources(args.sources)
    records = [
        probe_source(
            source,
            observer_id=args.observer_id,
            observer_host=args.observer_host,
            timeout=args.timeout,
        )
        for source in sources
    ]
    if args.output:
        append_jsonl(args.output, records)
    if args.pretty:
        print(json.dumps({"records": records}, indent=2))
    else:
        for record in records:
            print(json.dumps(record, sort_keys=True, separators=(",", ":")))
    return 0 if any(record["reachable"] for record in records) else 2


if __name__ == "__main__":
    raise SystemExit(main())
