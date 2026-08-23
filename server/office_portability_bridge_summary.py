#!/usr/bin/env python3
"""Produce privacy-preserving aggregate status for Ava Office and Number Portability.

The bridge deliberately reads the two commissioned loopback-only read APIs instead of
opening either service's private SQLite database. This preserves the database ownership
boundary and lets the signed Operations Center collector consume only the same sanitized
aggregate surfaces exposed to other local read-only consumers.

Keep this helper importable by the shared Operations Center collector's Python 3.6
compatibility check. Newer application services may use newer language features; this
small bridge deliberately does not.
"""

import argparse
import datetime as dt
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen

DEFAULT_AVA_URL = "http://127.0.0.1:8116/api/ava-office/summary"
DEFAULT_PORT_URL = "http://127.0.0.1:8117/api/portability/summary"
MAX_RESPONSE_BYTES = 65536


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _fetch_json(url):
    request = Request(url, headers={"Accept": "application/json"})
    with urlopen(request, timeout=2.0) as response:
        status = getattr(response, "status", response.getcode())
        if status != 200:
            raise ValueError("unexpected HTTP status")
        raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError("summary response is oversized")
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("summary response must be an object")
    return payload


def _count_map(value):
    if not isinstance(value, dict):
        raise ValueError("count map is invalid")
    output = {}
    for key, count in value.items():
        if not isinstance(key, str) or not key or len(key) > 64:
            raise ValueError("count key is invalid")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError("count value is invalid")
        output[key] = count
    return output


def _count(value):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("count is invalid")
    return value


def ava_summary(url=DEFAULT_AVA_URL, fetcher=None):
    reader = fetcher or _fetch_json
    try:
        payload = reader(url)
        if payload.get("mode") != "read-only":
            raise ValueError("Ava Office summary is not read-only")
        return {
            "available": True,
            "mode": "read-only",
            "execution_enabled": False,
            "autonomy_level": "gated",
            "work_items": _count_map(payload.get("work_items", {})),
            "actions": _count_map(payload.get("actions", {})),
            "standing_instructions": _count(payload.get("standing_instructions", 0)),
        }
    except Exception:
        return {
            "available": False,
            "mode": "read-only",
            "execution_enabled": False,
            "error": "summary_unavailable",
        }


def portability_summary(url=DEFAULT_PORT_URL, fetcher=None):
    reader = fetcher or _fetch_json
    try:
        payload = reader(url)
        if payload.get("mode") != "read-only":
            raise ValueError("portability summary is not read-only")
        if payload.get("submission_authorized") is not False:
            raise ValueError("port submission authorization must remain false")
        if payload.get("cutover_authorized") is not False:
            raise ValueError("port cutover authorization must remain false")
        return {
            "available": True,
            "mode": "read-only",
            "cases": _count_map(payload.get("cases", {})),
            "numbers": _count(payload.get("numbers", 0)),
            "documents": _count(payload.get("documents", 0)),
            "submission_authorized": False,
            "cutover_authorized": False,
        }
    except Exception:
        return {
            "available": False,
            "mode": "read-only",
            "submission_authorized": False,
            "cutover_authorized": False,
            "error": "summary_unavailable",
        }


def build_summary(ava_url=DEFAULT_AVA_URL, port_url=DEFAULT_PORT_URL, fetcher=None):
    return {
        "format": "wwcx-office-services-summary-v1",
        "generated_at": utc_now(),
        "ava_office": ava_summary(ava_url, fetcher=fetcher),
        "number_portability": portability_summary(port_url, fetcher=fetcher),
        "privacy": {
            "record_level_content_included": False,
            "telephone_numbers_included": False,
            "transcripts_or_audio_included": False,
            "document_references_included": False,
            "credentials_included": False,
        },
    }


def write_atomic(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(encoded)
    os.chmod(str(tmp), 0o600)
    os.replace(str(tmp), str(path))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ava-url", default=DEFAULT_AVA_URL)
    parser.add_argument("--portability-url", default=DEFAULT_PORT_URL)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = build_summary(args.ava_url, args.portability_url)
    if args.output:
        write_atomic(args.output, payload)
    else:
        print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
