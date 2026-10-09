#!/usr/bin/env python3
"""Build the bounded public status document consumed by WW.CX/CreekCo time pages."""

import argparse
import datetime as dt
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

SCHEMA_VERSION = 1


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def load_last_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.is_file():
        return None
    last = None  # type: Optional[Dict[str, Any]]
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        value = json.loads(line)
        if isinstance(value, dict):
            last = value
    return last


def load_json_records(path: Path):
    records = []
    if not path.is_file():
        return records
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        value = json.loads(line)
        if isinstance(value, dict):
            records.append(value)
    return records


def find_server(records, host):
    for record in records:
        if record.get("server_name") == host:
            return record
    return None


def bounded_ntp(record: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    result = {
        "reachable": False,
        "observed_at_utc": None,
        "resolved_address": None,
        "stratum": None,
        "rtt_ms": None,
        "clock_offset_ms": None,
        "leap_indicator": None,
        "ntp_version": None,
    }
    if not record:
        return result
    for key in result:
        if key in record:
            result[key] = record[key]
    return result


def bounded_nts(record: Optional[Dict[str, Any]], expected: bool) -> Dict[str, Any]:
    result = {
        "expected": expected,
        "reachable": False,
        "tls_verified": False,
        "alpn": None,
        "observed_at_utc": None,
        "rtt_ms": None,
        "certificate_not_after_utc": None,
    }
    if not record:
        return result
    for key in result:
        if key == "expected":
            continue
        if key in record:
            result[key] = record[key]
    return result


def write_atomic(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    os.chmod(str(temp), 0o600)
    os.replace(str(temp), str(path))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ntp-current", type=Path, required=True)
    parser.add_argument("--nts-current", type=Path, required=True)
    parser.add_argument("--nts-secondary-current", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--observer-id", default="business159")
    parser.add_argument("--observer-host", default="business159.web-hosting.com")
    parser.add_argument("--nts-expected", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ntp_records = load_json_records(args.ntp_current)
    ntp_record = find_server(ntp_records, "ntp.ww.cx") or (ntp_records[0] if ntp_records else None)
    ntp_secondary = find_server(ntp_records, "ntp2.ww.cx")
    nts_record = load_last_json(args.nts_current)
    nts_secondary = load_last_json(args.nts_secondary_current) if args.nts_secondary_current else None

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "service": {
            "canonical_host": "ntp.ww.cx",
            "alternate_hosts": ["time.ww.cx"],
            "ntp": {"transport": "udp", "port": 123},
            "nts": {"transport": "tcp", "port": 4460},
        },
        "observer": {
            "id": args.observer_id,
            "host": args.observer_host,
        },
        "ntp": bounded_ntp(ntp_record),
        "nts": bounded_nts(nts_record, args.nts_expected),
        "endpoints": {
            "primary": {"host": "ntp.ww.cx", "role": "primary", "ntp": bounded_ntp(ntp_record), "nts": bounded_nts(nts_record, args.nts_expected)},
            "secondary": {"host": "ntp2.ww.cx", "role": "secondary", "ntp": bounded_ntp(ntp_secondary), "nts": bounded_nts(nts_secondary, True)},
        },
    }
    write_atomic(args.output, payload)
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
