#!/usr/bin/env python3
"""Read-only SQLite FTS5 search engine for the Edge1 Private Library."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", re.I),
    re.compile(r"\b(?:api[_ -]?key|access[_ -]?token|secret[_ -]?token|password)\b\s*[:=]", re.I),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
)

@dataclass(frozen=True)
class SearchResult:
    document_id: str
    collection: str
    title: str
    source_path: str
    classification: str
    chunk_index: int
    locator: str
    excerpt: str
    score: float
    updated_at: str = ""

def contains_secret(text: str) -> bool:
    value = str(text or "")
    return any(pattern.search(value) for pattern in SECRET_PATTERNS)

def _fts_query(query: str) -> str:
    terms = re.findall(r"[A-Za-z0-9][A-Za-z0-9_.:/@+-]*", query or "")
    return " AND ".join('"' + term.replace('"', '""') + '"' for term in terms[:16])

def _excerpt(text: str, limit: int) -> str:
    value = " ".join(str(text or "").split())
    if limit <= 0 or len(value) <= limit:
        return value
    return value[: max(0, limit - 1)].rstrip() + "…"

def search_library(db_path: str | Path, query: str, collections: Iterable[str], *, limit: int = 6, excerpt_chars: int = 1000) -> list[SearchResult]:
    path = Path(db_path)
    if not path.is_file():
        raise FileNotFoundError(path)
    if contains_secret(query):
        return []

    collection_list = [str(item).strip() for item in collections if str(item).strip()]
    if not collection_list:
        return []

    bounded_limit = min(max(int(limit), 1), 50)
    placeholders = ",".join("?" for _ in collection_list)
    fts = _fts_query(query)

    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
    connection.row_factory = sqlite3.Row
    try:
        if fts:
            sql = f"""
                SELECT d.id AS document_id, d.collection, d.title, d.source_path,
                       d.classification, d.updated_at, c.chunk_index, c.locator,
                       c.text, bm25(chunks_fts) AS score
                FROM chunks_fts
                JOIN chunks c ON c.id = chunks_fts.rowid
                JOIN documents d ON d.id = c.document_id
                WHERE chunks_fts MATCH ?
                  AND d.collection IN ({placeholders})
                ORDER BY score ASC, d.updated_at DESC, d.id, c.chunk_index
                LIMIT ?
            """
            params = [fts, *collection_list, bounded_limit]
        else:
            sql = f"""
                SELECT d.id AS document_id, d.collection, d.title, d.source_path,
                       d.classification, d.updated_at, c.chunk_index, c.locator,
                       c.text, 0.0 AS score
                FROM chunks c
                JOIN documents d ON d.id = c.document_id
                WHERE d.collection IN ({placeholders})
                ORDER BY d.updated_at DESC, d.id, c.chunk_index
                LIMIT ?
            """
            params = [*collection_list, bounded_limit]
        rows = connection.execute(sql, params).fetchall()
    finally:
        connection.close()

    return [
        SearchResult(
            document_id=row["document_id"],
            collection=row["collection"],
            title=row["title"],
            source_path=row["source_path"],
            classification=row["classification"],
            chunk_index=int(row["chunk_index"]),
            locator=row["locator"] or "",
            excerpt=_excerpt(row["text"], int(excerpt_chars)),
            score=float(row["score"] or 0),
            updated_at=row["updated_at"] or "",
        )
        for row in rows
    ]
