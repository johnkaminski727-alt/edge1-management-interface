"""Read-only query model for the private WW.CX NNTP News Reader."""

from __future__ import annotations

import json
import re
from typing import Any

from .storage import CommsStore

MESSAGE_ID_TOKEN_RE = re.compile(r'<[^<>\s@]+@[^<>\s@]+>')


def _thread_metadata(item: dict[str, Any]) -> dict[str, Any]:
    try:
        headers = json.loads(str(item.pop('headers_json')))
    except (json.JSONDecodeError, TypeError, ValueError):
        headers = {}
    stored_refs = str(item.get('references_text') or '').strip()
    upstream_refs = str(headers.get('X-WWCX-Upstream-References') or '').strip()
    references = stored_refs or upstream_refs
    message_ids = MESSAGE_ID_TOKEN_RE.findall(references)
    identity = str(item.get('source_item_id') or item.get('message_id') or item.get('id'))
    item['thread_key'] = message_ids[0] if message_ids else identity
    item['thread_parent'] = message_ids[-1] if message_ids else None
    item['thread_depth'] = len(message_ids)
    item['thread_references'] = message_ids
    return item


def list_news_page(
    store: CommsStore,
    group_name: str,
    *,
    limit: int = 50,
    offset: int = 0,
    search: str = '',
    source: str = '',
) -> dict[str, Any]:
    """Return one bounded article page plus pagination, source counts, and thread metadata."""
    limit = max(1, min(int(limit), 100))
    offset = max(0, int(offset))
    term = search.strip()[:256]
    source_filter = source.strip()[:128]

    base_clauses = ['a.group_name=?']
    base_args: list[Any] = [group_name]
    if term:
        needle = f'%{term}%'
        base_clauses.append(
            '''(
                a.subject LIKE ? COLLATE NOCASE OR
                a.author LIKE ? COLLATE NOCASE OR
                a.message_id LIKE ? COLLATE NOCASE OR
                COALESCE(i.source_name,'') LIKE ? COLLATE NOCASE OR
                COALESCE(i.source_item_id,'') LIKE ? COLLATE NOCASE
            )'''
        )
        base_args.extend([needle] * 5)

    clauses = list(base_clauses)
    args = list(base_args)
    if source_filter == 'native':
        clauses.append('i.source_name IS NULL')
    elif source_filter:
        clauses.append('i.source_name=?')
        args.append(source_filter)

    where = ' AND '.join(clauses)
    source_where = ' AND '.join(base_clauses)

    with store.connect() as conn:
        total = int(
            conn.execute(
                f'''SELECT COUNT(*)
                    FROM articles a
                    LEFT JOIN ingest_items i ON i.article_id=a.id
                    WHERE {where}''',
                args,
            ).fetchone()[0]
        )
        source_rows = conn.execute(
            f'''SELECT i.source_name,COUNT(*) AS count
                FROM articles a
                LEFT JOIN ingest_items i ON i.article_id=a.id
                WHERE {source_where}
                GROUP BY i.source_name
                ORDER BY count DESC, i.source_name''',
            base_args,
        ).fetchall()
        rows = conn.execute(
            f'''SELECT a.id,a.group_name,a.message_id,a.author,a.subject,a.date_rfc5322,
                       a.references_text,a.created_at_utc,a.headers_json,
                       i.source_name,i.source_item_id
                FROM articles a
                LEFT JOIN ingest_items i ON i.article_id=a.id
                WHERE {where}
                ORDER BY a.id DESC
                LIMIT ? OFFSET ?''',
            [*args, limit, offset],
        ).fetchall()

    articles = [_thread_metadata(dict(row)) for row in rows]
    returned = len(articles)
    next_offset = offset + returned if offset + returned < total else None
    previous_offset = max(0, offset - limit) if offset > 0 else None
    source_counts = [
        {'source_name': row['source_name'], 'count': int(row['count'])}
        for row in source_rows
    ]
    return {
        'articles': articles,
        'pagination': {
            'total': total,
            'limit': limit,
            'offset': offset,
            'returned': returned,
            'has_previous': previous_offset is not None,
            'has_next': next_offset is not None,
            'previous_offset': previous_offset,
            'next_offset': next_offset,
        },
        'source_counts': source_counts,
    }
