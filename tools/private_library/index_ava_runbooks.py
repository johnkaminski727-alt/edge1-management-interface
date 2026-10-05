#!/usr/bin/env python3
"""Index an explicit list of repository runbooks into AVA's operations library."""
import argparse
import hashlib
import importlib.util
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ALLOWED = (
    "docs/handoff/private-library-search-live-direct.md",
    "docs/handoff/private-library-backup-runbook.md",
    "docs/handoff/private-library-search-service-runbook.md",
)

def index(db, root=ROOT):
    spec = importlib.util.spec_from_file_location("ava_index_engine", root / "services/bigbird-ai-gateway/app/library_engine.py")
    engine = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = engine
    spec.loader.exec_module(engine)
    sources = []
    for relative in ALLOWED:
        path = (root / relative).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            raise ValueError("invalid approved source")
        if path.stat().st_size > 256 * 1024:
            raise ValueError("source exceeds indexing limit")
        text = path.read_text()
        if engine.contains_secret(text):
            raise ValueError("source failed secret guard: " + relative)
        title = next((line.lstrip("# ").strip() for line in text.splitlines() if line.startswith("# ")), path.stem)
        sources.append((relative, title, text, datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()))
    manifest = []
    with sqlite3.connect(db) as c:
        c.execute("PRAGMA foreign_keys=ON")
        for relative, title, text, stamp in sources:
            ident = hashlib.sha256(relative.encode()).hexdigest()
            c.execute("""INSERT INTO documents VALUES (?, 'operations', ?, ?, 'internal', ?)
                         ON CONFLICT(id) DO UPDATE SET title=excluded.title,
                         source_path=excluded.source_path, updated_at=excluded.updated_at""",
                      (ident, title, relative, stamp))
            c.execute("DELETE FROM chunks WHERE document_id=?", (ident,))
            chunks = [text[i:i+2400] for i in range(0, len(text), 2200)]
            for i, chunk in enumerate(chunks):
                c.execute("INSERT INTO chunks(document_id,chunk_index,locator,text) VALUES (?,?,?,?)",
                          (ident, i, "characters " + str(i*2200) + "–" + str(min(i*2200+2400,len(text))), chunk))
            manifest.append({"path": relative, "sha256": hashlib.sha256(text.encode()).hexdigest(), "chunks": len(chunks)})
        if c.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("library integrity check failed")
    return manifest

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    args = parser.parse_args()
    if not args.db.is_file():
        parser.error("existing library database required")
    print(json.dumps(index(args.db), indent=2))
