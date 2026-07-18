#!/usr/bin/env python3
"""Serve the read-only WW.CX Time Authority dashboard and summary API."""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import os
import urllib.parse
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = REPO_ROOT / "src" / "web" / "time-authority"
BASELINE_PATH = REPO_ROOT / "modules" / "time-authority" / "fixtures" / "baseline-measurements.json"
SOURCES_PATH = REPO_ROOT / "modules" / "time-authority" / "config" / "sources.json"
DEFAULT_DATA_PATH = Path("/var/lib/edge1-time-authority/measurements.jsonl")


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def clamp_limit(raw: str | None) -> int:
    try:
        value = int(raw or 500)
    except ValueError:
        value = 500
    return max(10, min(value, 5000))


def configured_data_paths() -> list[Path]:
    raw = os.environ.get("EDGE1_TIME_AUTHORITY_DATA_PATHS", "").strip()
    return [Path(item) for item in raw.split(os.pathsep) if item] if raw else [DEFAULT_DATA_PATH]


def normalize_record(record: dict[str, Any]) -> dict[str, Any] | None:
    required = {"observer_id", "observer_host", "source_id", "server_name", "reachable"}
    if not required.issubset(record):
        return None
    normalized = dict(record)
    normalized.setdefault("schema_version", 1)
    normalized.setdefault("observed_at_utc", None)
    normalized.setdefault("resolved_address", None)
    normalized.setdefault("stratum", None)
    normalized.setdefault("refid", None)
    normalized.setdefault("rtt_ms", None)
    normalized.setdefault("clock_offset_ms", None)
    normalized.setdefault("root_delay_ms", None)
    normalized.setdefault("root_dispersion_ms", None)
    normalized.setdefault("expectation_ok", bool(normalized["reachable"]))
    normalized.setdefault("error", None)
    return normalized


def read_jsonl(path: Path, limit: int) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    lines: collections.deque[str] = collections.deque(maxlen=limit)
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if len(line) <= 64_000:
                lines.append(line)
    records: list[dict[str, Any]] = []
    for line in lines:
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            record = normalize_record(value)
            if record is not None:
                records.append(record)
    return records


def load_baseline() -> list[dict[str, Any]]:
    payload = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    date = str(payload.get("captured_date_utc", ""))
    records: list[dict[str, Any]] = []
    for raw in payload.get("records", []):
        if not isinstance(raw, dict):
            continue
        raw = dict(raw)
        raw["observed_at_utc"] = date + "T00:00:00Z" if date else None
        raw["expectation_ok"] = bool(raw.get("reachable"))
        record = normalize_record(raw)
        if record is not None:
            records.append(record)
    return records


def load_records(paths: Iterable[Path], limit: int) -> tuple[str, list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    for path in paths:
        records.extend(read_jsonl(path, limit))
    if records:
        return "live", records[-limit:]
    return "baseline", load_baseline()


def source_catalog() -> list[dict[str, Any]]:
    payload = json.loads(SOURCES_PATH.read_text(encoding="utf-8"))
    return [item for item in payload.get("sources", []) if isinstance(item, dict)]


def latest_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    for record in records:
        latest[(str(record["observer_id"]), str(record["source_id"]))] = record
    return sorted(latest.values(), key=lambda item: (str(item["observer_id"]), str(item["source_id"])))


def observer_summary(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for record in latest_records(records):
        grouped[str(record["observer_id"])].append(record)
    summaries: list[dict[str, Any]] = []
    for observer_id, items in sorted(grouped.items()):
        reachable = [item for item in items if item.get("reachable")]
        rtts = [float(item["rtt_ms"]) for item in reachable if item.get("rtt_ms") is not None]
        summaries.append(
            {
                "observer_id": observer_id,
                "observer_host": items[0].get("observer_host"),
                "reachable_sources": len(reachable),
                "total_sources": len(items),
                "average_rtt_ms": round(sum(rtts) / len(rtts), 3) if rtts else None,
                "minimum_rtt_ms": round(min(rtts), 3) if rtts else None,
                "expectations_met": sum(1 for item in items if item.get("expectation_ok")),
            }
        )
    return summaries


def summary_payload(limit: int) -> dict[str, Any]:
    mode, records = load_records(configured_data_paths(), limit)
    records = sorted(records, key=lambda item: str(item.get("observed_at_utc") or ""))
    return {
        "schema_version": 1,
        "generated_at_utc": utc_now(),
        "mode": mode,
        "sources": source_catalog(),
        "observers": observer_summary(records),
        "latest": latest_records(records),
        "history": records,
    }


class TimeAuthorityHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        super().end_headers()

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/time-authority/summary":
            params = urllib.parse.parse_qs(parsed.query)
            self.send_json(HTTPStatus.OK, summary_payload(clamp_limit(params.get("limit", [None])[0])))
            return
        if parsed.path == "/healthz":
            self.send_json(HTTPStatus.OK, {"ok": True, "service": "edge1-time-authority", "read_only": True})
            return
        super().do_GET()

    def send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8092)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    server = ThreadingHTTPServer((args.host, args.port), TimeAuthorityHandler)
    print(f"Serving WW.CX Time Authority on http://{args.host}:{args.port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
