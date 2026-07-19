#!/usr/bin/env python3
"""Local WW.CX numbering intelligence service.

The HTTP service is deliberately read-only and binds to loopback by default.
Dataset import and source removal are explicit offline operator actions.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Iterable, Optional
from urllib.parse import parse_qs, urlparse

DIGITS = re.compile(r"\D+")
SOURCE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_nanp(value: str) -> str:
    digits = DIGITS.sub("", value)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        raise ValueError("expected a ten-digit NANP number")
    if digits[0] in "01" or digits[3] in "01":
        raise ValueError("invalid NANP NPA or NXX")
    return digits


def validate_source(source: str) -> str:
    if not SOURCE_NAME.fullmatch(source):
        raise ValueError(
            "source must be 1-128 characters using letters, digits, dot, underscore, or hyphen"
        )
    return source


def connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS prefixes (
                npa TEXT NOT NULL,
                nxx TEXT NOT NULL,
                country TEXT,
                region TEXT,
                rate_center TEXT,
                ocn TEXT,
                company TEXT,
                status TEXT,
                source TEXT NOT NULL,
                source_updated TEXT,
                imported_at TEXT NOT NULL,
                PRIMARY KEY (npa, nxx, source)
            );
            CREATE INDEX IF NOT EXISTS idx_prefixes_npa_nxx
                ON prefixes(npa, nxx);
            CREATE INDEX IF NOT EXISTS idx_prefixes_ocn
                ON prefixes(ocn);
            CREATE INDEX IF NOT EXISTS idx_prefixes_source
                ON prefixes(source);
            """
        )
        conn.execute(
            "INSERT OR REPLACE INTO metadata(key,value) VALUES('schema_version','2')"
        )


def first(row: Dict[str, str], *names: str) -> str:
    folded = {str(k).strip().lower(): (v or "").strip() for k, v in row.items()}
    for name in names:
        value = folded.get(name.lower(), "")
        if value:
            return value
    return ""


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def import_rows(
    path: Path,
    source: str,
    rows: Iterable[Dict[str, str]],
    *,
    replace_source: bool = False,
    checksum: str = "",
) -> Dict[str, Any]:
    source = validate_source(source)
    imported_at = utc_now()
    imported = 0
    rejected = 0

    with connect(path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        if replace_source:
            conn.execute("DELETE FROM prefixes WHERE source=?", (source,))

        for row in rows:
            npa = first(row, "npa", "area code")
            nxx = first(row, "nxx", "central office code", "co code")
            if not (
                re.fullmatch(r"[2-9][0-9]{2}", npa)
                and re.fullmatch(r"[2-9][0-9]{2}", nxx)
            ):
                rejected += 1
                continue
            conn.execute(
                """
                INSERT OR REPLACE INTO prefixes
                (npa,nxx,country,region,rate_center,ocn,company,status,source,source_updated,imported_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    npa,
                    nxx,
                    first(row, "country"),
                    first(row, "region", "state", "province"),
                    first(row, "rate center", "rate_center"),
                    first(row, "ocn"),
                    first(row, "company", "assignee", "service provider"),
                    first(row, "status"),
                    source,
                    first(row, "source updated", "effective date", "assignment date"),
                    imported_at,
                ),
            )
            imported += 1

        metadata = {
            f"last_import:{source}": imported_at,
            f"last_import_count:{source}": str(imported),
            f"last_rejected_count:{source}": str(rejected),
        }
        if checksum:
            metadata[f"last_sha256:{source}"] = checksum
        for key, value in metadata.items():
            conn.execute(
                "INSERT OR REPLACE INTO metadata(key,value) VALUES(?,?)",
                (key, value),
            )

    return {
        "source": source,
        "imported": imported,
        "rejected": rejected,
        "replace_source": replace_source,
        "imported_at": imported_at,
        "sha256": checksum or None,
    }


def remove_source(path: Path, source: str) -> Dict[str, Any]:
    source = validate_source(source)
    with connect(path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        removed = conn.execute(
            "DELETE FROM prefixes WHERE source=?", (source,)
        ).rowcount
        conn.execute("DELETE FROM metadata WHERE key LIKE ?", (f"%:{source}",))
    return {"source": source, "removed": removed}


def list_sources(path: Path) -> list[Dict[str, Any]]:
    with connect(path) as conn:
        rows = conn.execute(
            """
            SELECT source, COUNT(*) AS prefixes, MAX(imported_at) AS imported_at
            FROM prefixes
            GROUP BY source
            ORDER BY source
            """
        ).fetchall()
        metadata_rows = conn.execute(
            "SELECT key,value FROM metadata WHERE key LIKE '%:%'"
        ).fetchall()
    metadata = {row["key"]: row["value"] for row in metadata_rows}
    result = []
    for row in rows:
        source = row["source"]
        result.append(
            {
                "source": source,
                "prefixes": row["prefixes"],
                "imported_at": row["imported_at"],
                "sha256": metadata.get(f"last_sha256:{source}"),
                "last_rejected": int(metadata.get(f"last_rejected_count:{source}", "0")),
            }
        )
    return result


def lookup(path: Path, number: str) -> Optional[Dict[str, Any]]:
    normalized = normalize_nanp(number)
    with connect(path) as conn:
        rows = conn.execute(
            "SELECT * FROM prefixes WHERE npa=? AND nxx=? ORDER BY source",
            (normalized[:3], normalized[3:6]),
        ).fetchall()
    if not rows:
        return None
    return {
        "number": normalized,
        "npa": normalized[:3],
        "nxx": normalized[3:6],
        "assignments": [dict(row) for row in rows],
    }


class Handler(BaseHTTPRequestHandler):
    database: Path

    def send_json(self, status: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/healthz":
            with connect(self.database) as conn:
                total = conn.execute("SELECT COUNT(*) FROM prefixes").fetchone()[0]
                source_total = conn.execute(
                    "SELECT COUNT(DISTINCT source) FROM prefixes"
                ).fetchone()[0]
            self.send_json(
                200,
                {
                    "status": "ok",
                    "prefixes": total,
                    "sources": source_total,
                    "time": utc_now(),
                },
            )
            return
        if parsed.path == "/v1/lookup":
            number = parse_qs(parsed.query).get("number", [""])[0]
            try:
                result = lookup(self.database, number)
            except ValueError as exc:
                self.send_json(400, {"error": "invalid_number", "detail": str(exc)})
                return
            if result is None:
                self.send_json(404, {"error": "not_found"})
                return
            self.send_json(200, result)
            return
        self.send_json(404, {"error": "not_found"})

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"{self.address_string()} - {fmt % args}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--database",
        type=Path,
        default=Path("/var/lib/wwcx-numbering-node/numbering.sqlite3"),
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init")

    importer = sub.add_parser("import-csv")
    importer.add_argument("--source", required=True)
    importer.add_argument(
        "--replace-source",
        action="store_true",
        help="atomically remove existing rows for this source before importing",
    )
    importer.add_argument("csv_file", type=Path)

    remover = sub.add_parser("remove-source")
    remover.add_argument("source")

    sub.add_parser("list-sources")

    serve = sub.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8093)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db(args.database)
    if args.command == "init":
        return 0
    if args.command == "import-csv":
        checksum = file_sha256(args.csv_file)
        with args.csv_file.open("r", encoding="utf-8-sig", newline="") as handle:
            result = import_rows(
                args.database,
                args.source,
                csv.DictReader(handle),
                replace_source=args.replace_source,
                checksum=checksum,
            )
        print(json.dumps(result, sort_keys=True))
        return 0
    if args.command == "remove-source":
        print(json.dumps(remove_source(args.database, args.source), sort_keys=True))
        return 0
    if args.command == "list-sources":
        print(json.dumps({"sources": list_sources(args.database)}, sort_keys=True))
        return 0

    Handler.database = args.database
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"WW.CX numbering node listening on http://{args.host}:{args.port}")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
