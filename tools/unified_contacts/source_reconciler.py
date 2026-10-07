#!/usr/bin/env python3
"""Unified Contacts source reconciliation with Private Library lookup enabled."""
from __future__ import annotations

from pathlib import Path

if __package__:
    from .source_reconciler_impl import *  # noqa: F401,F403
    from .source_reconciler_impl import reconcile as _reconcile
else:
    from source_reconciler_impl import *  # noqa: F401,F403
    from source_reconciler_impl import reconcile as _reconcile

DEFAULT_PRIVATE_LIBRARY_DB = Path('/var/lib/bigbird-ai-library/library.sqlite3')


def reconcile(connection, roots, now, apply=False, library_db=None):
    """Reconcile local, web, and Private Library evidence locations."""
    if library_db is None:
        library_db = DEFAULT_PRIVATE_LIBRARY_DB
    return _reconcile(
        connection,
        roots,
        now,
        apply=apply,
        library_db=Path(library_db),
    )
