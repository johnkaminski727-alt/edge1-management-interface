#!/usr/bin/env python3
"""Unified Contacts source reconciliation with Private Library and recovery hints."""
from __future__ import annotations

import json
from pathlib import Path

if __package__:
    from .source_reconciler_impl import *  # noqa: F401,F403
    from .source_reconciler_impl import reconcile as _reconcile
else:
    from source_reconciler_impl import *  # noqa: F401,F403
    from source_reconciler_impl import reconcile as _reconcile

DEFAULT_PRIVATE_LIBRARY_DB = Path('/var/lib/bigbird-ai-library/library.sqlite3')
DEFAULT_HINTS = Path(__file__).resolve().parents[2] / 'config' / 'contacts' / 'evidence-source-hints.json'


def _load_recovery_hints(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return []
    hints = payload.get('hints', []) if isinstance(payload, dict) else []
    return [item for item in hints if isinstance(item, dict)]


def reconcile(connection, roots, now, apply=False, library_db=None, hints_path=None):
    """Reconcile local/web/Private Library sources and stage alternate-source hints.

    Recovery hints never replace the missing original source. They are returned
    as AUTO_STAGE candidates so the maintenance layer can expose them for review.
    """
    if library_db is None:
        library_db = DEFAULT_PRIVATE_LIBRARY_DB
    result = _reconcile(
        connection,
        roots,
        now,
        apply=apply,
        library_db=Path(library_db),
    )

    known_pids = {int(item['provenance_id']) for item in result['results']}
    path = Path(hints_path) if hints_path else DEFAULT_HINTS
    added = 0
    for hint in _load_recovery_hints(path):
        try:
            pid = int(hint.get('provenance_id'))
        except (TypeError, ValueError):
            continue
        if pid not in known_pids:
            continue
        location = str(hint.get('location') or '').strip()
        if not location:
            continue
        result['results'].append({
            'provenance_id': pid,
            'status': 'candidate',
            'action_level': 'AUTO_STAGE',
            'location_kind': 'internal_reference',
            'location': location,
            'match_method': f"recovery_hint:{hint.get('source_system','external')}",
            'source_sha256': None,
            'label': str(hint.get('label') or ''),
            'match_basis': str(hint.get('match_basis') or ''),
            'confidence': str(hint.get('confidence') or 'unverified'),
            'source_type': str(hint.get('source_type') or 'alternate_source'),
            'needs_update': False,
        })
        added += 1

    result['recovery_hints'] = added
    result['candidates'] = sum(1 for item in result['results'] if item['status'] == 'candidate')
    result['ambiguous'] = sum(1 for item in result['results'] if item['status'] == 'ambiguous')
    result['missing'] = sum(1 for item in result['results'] if item['status'] == 'missing')
    return result
