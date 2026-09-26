#!/usr/bin/env python3
"""Localhost-only, read-only Edge1 backup dashboard API.

Reads *sanitized* backup status manifests from a private directory. Never reads
archives, credentials or Dropbox tokens, and never starts backup/restore jobs.
"""
import argparse
import json
import os
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

WEB = Path(__file__).resolve().parents[1] / "src" / "web" / "backup-recovery"
MAX_MANIFESTS = 100
MAX_BYTES = 65536
ALLOWED_STATES = {"verified", "uploaded", "failed", "unknown", "pending"}

def parse_date(value):
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            return None
        return stamp.astimezone(timezone.utc)
    except (ValueError, AttributeError, TypeError):
        return None

def sanitized_record(raw):
    """Fail closed on malformed metadata; never return unrecognized fields."""
    if not isinstance(raw, dict):
        return None
    name = raw.get("archive", "")
    stamp = raw.get("created_at", "")
    if not isinstance(name, str) or not name.endswith(".tar.gz.gpg") or len(name) > 160:
        return None
    if "/" in name or "\\" in name or not parse_date(stamp):
        return None
    def state(key):
        value = raw.get(key, "unknown")
        return value if value in ALLOWED_STATES else "unknown"
    bytes_value = raw.get("size_bytes")
    if not isinstance(bytes_value, int) or isinstance(bytes_value, bool) or not 0 <= bytes_value <= 10**13:
        bytes_value = None
    return {
        "archive": name,
        "created_at": parse_date(stamp).isoformat().replace("+00:00", "Z"),
        "size_bytes": bytes_value,
        "upload": state("upload"),
        "integrity": state("integrity"),
        "restore_test": state("restore_test"),
    }

def load_status(directory):
    records = []
    if directory.is_dir():
        for path in sorted(directory.glob("*.json"), reverse=True)[:MAX_MANIFESTS]:
            try:
                if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_BYTES:
                    continue
                record = sanitized_record(json.loads(path.read_text(encoding="utf-8")))
                if record:
                    records.append(record)
            except (OSError, ValueError, UnicodeError):
                continue
    records.sort(key=lambda x: x["created_at"], reverse=True)
    last = records[0] if records else None
    return {
        "schema_version": 1,
        "source": "local_sanitized_manifests",
        "last_backup": last["created_at"] if last else None,
        "records": records,
        "read_only": True,
        "notice": "An uploaded archive is not proof of completeness or successful restoration.",
    }

def handler_factory(directory):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = urlsplit(self.path).path
            if path == "/api/backups/status":
                data = json.dumps(load_status(directory)).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
            elif path in ("/", "/index.html"):
                data = (WEB / "index.html").read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
            else:
                self.send_error(404)
                return
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(data)
    return Handler

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1", choices=["127.0.0.1", "::1"])
    parser.add_argument("--port", type=int, default=8108)
    parser.add_argument("--manifest-dir", default=os.environ.get("EDGE1_BACKUP_MANIFEST_DIR", "/var/lib/edge1-backup-dashboard/manifests"))
    args = parser.parse_args()
    directory = Path(args.manifest_dir).resolve()
    print("Read-only backup console at http://%s:%d ; manifests: %s" % (args.host, args.port, directory))
    ThreadingHTTPServer((args.host, args.port), handler_factory(directory)).serve_forever()

if __name__ == "__main__":
    main()
