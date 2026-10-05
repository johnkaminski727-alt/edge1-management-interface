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

STOP_WORDS = frozenset("a an the and or i me my we our you your it its is are was were be been to of for from in on at by with do does did how what when where which can could would should please tell show about".split())

def _query_terms(query: str) -> list[str]:
    terms = re.findall(r"[^\W_]+(?:[_.:/@+-][^\W_]+)*", query or "", re.UNICODE)
    return list(dict.fromkeys(term.casefold() for term in terms
                             if term.casefold() not in STOP_WORDS))[:16]

def _fts_query(query: str, *, broad: bool = False) -> str:
    return (" OR " if broad else " AND ").join(
        '"' + term.replace('"', '""') + '"' for term in _query_terms(query))

def _excerpt(text: str, limit: int, query: str = "") -> str:
    value = " ".join(str(text or "").split())
    limit = min(max(int(limit), 80), 4000)
    if len(value) <= limit:
        return value
    hits = [value.casefold().find(term) for term in _query_terms(query)]
    hits = [hit for hit in hits if hit >= 0]
    start = max(0, min(hits) - limit // 4) if hits else 0
    end = min(len(value), start + limit - (1 if start else 0) - 1)
    return ("…" if start else "") + value[start:end].strip() + ("…" if end < len(value) else "")

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
    strict_fts = _fts_query(query)
    broad_fts = _fts_query(query, broad=True)
    if query.strip() and not strict_fts:
        return []

    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
    connection.row_factory = sqlite3.Row
    try:
        if not strict_fts:
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
            rows = connection.execute(sql, [*collection_list, bounded_limit]).fetchall()
        else:
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
            # Precision first. If a multi-term AND query under-fills the result set,
            # broaden to OR and merge unseen chunks. This improves recall for natural
            # language questions without displacing exact matches.
            rows = list(connection.execute(sql, [strict_fts, *collection_list, bounded_limit]).fetchall())
            if len(rows) < bounded_limit and broad_fts != strict_fts:
                broad_rows = connection.execute(sql, [broad_fts, *collection_list, bounded_limit * 3]).fetchall()
                seen = {(row["document_id"], int(row["chunk_index"])) for row in rows}
                for row in broad_rows:
                    key = (row["document_id"], int(row["chunk_index"]))
                    if key in seen:
                        continue
                    rows.append(row)
                    seen.add(key)
                    if len(rows) >= bounded_limit:
                        break
    finally:
        connection.close()

    rows = [row for row in rows if not contains_secret(" ".join(str(row[key] or "") for key in ("text", "title", "source_path")))]
    return [
        SearchResult(
            document_id=row["document_id"],
            collection=row["collection"],
            title=row["title"],
            source_path=row["source_path"],
            classification=row["classification"],
            chunk_index=int(row["chunk_index"]),
            locator=row["locator"] or "",
            excerpt=_excerpt(row["text"], int(excerpt_chars), query),
            score=float(row["score"] or 0),
            updated_at=row["updated_at"] or "",
        )
        for row in rows[:bounded_limit]
    ]
