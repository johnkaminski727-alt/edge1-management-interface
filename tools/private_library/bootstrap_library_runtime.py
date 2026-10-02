#!/usr/bin/env python3
"""Create or validate the Edge1 Private Library SQLite/FTS5 runtime database."""

from __future__ import annotations

import argparse
import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    collection TEXT NOT NULL,
    title TEXT NOT NULL,
    source_path TEXT NOT NULL,
    classification TEXT NOT NULL DEFAULT 'internal',
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    locator TEXT NOT NULL DEFAULT '',
    text TEXT NOT NULL,
    UNIQUE(document_id, chunk_index)
);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    text, content='chunks', content_rowid='id', tokenize='unicode61'
);
CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
    INSERT INTO chunks_fts(rowid, text) VALUES (new.id, new.text);
END;
CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, text) VALUES ('delete', old.id, old.text);
END;
CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, text) VALUES ('delete', old.id, old.text);
    INSERT INTO chunks_fts(rowid, text) VALUES (new.id, new.text);
END;
CREATE INDEX IF NOT EXISTS idx_documents_collection ON documents(collection);
CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id, chunk_index);
"""

BOOTSTRAP_TITLE = "Edge1 Private Library runtime bootstrap"
BOOTSTRAP_PATH = "operations/private-library-runtime-bootstrap.md"
BOOTSTRAP_TEXT = (
    "Edge1 Private Library runtime bootstrap evidence. "
    "The operations collection is available for read-only FTS5 search. "
    "VPN and private access documentation can be indexed here after source approval. "
    "This bootstrap record contains no credentials or private user data."
)

def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def bootstrap_id() -> str:
    return hashlib.sha256(BOOTSTRAP_PATH.encode("utf-8")).hexdigest()

def create_or_validate(path: Path, seed: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    try:
        con.executescript(SCHEMA)
        con.execute("PRAGMA foreign_keys=ON")
        if seed:
            doc_id = bootstrap_id()
            now = utc_now()
            con.execute(
                """
                INSERT INTO documents(id, collection, title, source_path, classification, updated_at)
                VALUES (?, 'operations', ?, ?, 'internal', ?)
                ON CONFLICT(id) DO UPDATE SET
                    title=excluded.title,
                    source_path=excluded.source_path,
                    classification=excluded.classification,
                    updated_at=excluded.updated_at
                """,
                (doc_id, BOOTSTRAP_TITLE, BOOTSTRAP_PATH, now),
            )
            con.execute(
                """
                INSERT INTO chunks(document_id, chunk_index, locator, text)
                VALUES (?, 0, 'bootstrap', ?)
                ON CONFLICT(document_id, chunk_index) DO UPDATE SET
                    locator=excluded.locator,
                    text=excluded.text
                """,
                (doc_id, BOOTSTRAP_TEXT),
            )
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"SQLite integrity_check failed: {integrity}")
        fts_count = con.execute("SELECT COUNT(*) FROM chunks_fts").fetchone()[0]
        chunk_count = con.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        if fts_count != chunk_count:
            con.execute("INSERT INTO chunks_fts(chunks_fts) VALUES ('rebuild')")
            fts_count = con.execute("SELECT COUNT(*) FROM chunks_fts").fetchone()[0]
            if fts_count != chunk_count:
                raise RuntimeError("FTS5 index count does not match chunk count")
        con.commit()
    finally:
        con.close()

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--seed-bootstrap", action="store_true")
    args = parser.parse_args()
    create_or_validate(args.db, args.seed_bootstrap)
    print(f"Private Library database ready: {args.db}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
