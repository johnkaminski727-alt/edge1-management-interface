#!/usr/bin/env python3
"""Disposable general Edge1 SQLite recovery rehearsal.

Creates transactionally consistent snapshots of representative live databases,
restores those snapshots into a second disposable location, validates SQLite
integrity/schema parity, then removes all disposable database copies. No live
service or production database is modified.
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATUS = Path('/var/www/edge1-status/recovery-rehearsal/status.json')
WORK_ROOT = Path('/var/lib/edge1-recovery-rehearsal')
DATABASES = {
    'mail_correspondence': Path('/var/lib/wwcx-mail-room/correspondence.sqlite3'),
    'mail_security': Path('/var/lib/wwcx-mail-security/security.sqlite3'),
    'contacts': Path('/var/lib/edge1-phone-intelligence/phone-intelligence.sqlite'),
    'contacts_maintenance': Path('/var/lib/edge1-contacts-maintenance/maintenance.sqlite'),
    'private_library': Path('/var/lib/bigbird-ai-library/library.sqlite3'),
    'navigation': Path('/var/lib/edge1-navigation/navigation.sqlite3'),
}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def inspect(path: Path) -> dict:
    with sqlite3.connect(f'file:{path}?mode=ro', uri=True, timeout=20) as db:
        integrity = db.execute('PRAGMA integrity_check').fetchone()[0]
        tables = db.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchone()[0]
        pages = db.execute('PRAGMA page_count').fetchone()[0]
        user_version = db.execute('PRAGMA user_version').fetchone()[0]
    return {'integrity': integrity, 'tables': int(tables), 'pages': int(pages), 'user_version': int(user_version)}


def snapshot(source: Path, target: Path) -> None:
    with sqlite3.connect(f'file:{source}?mode=ro', uri=True, timeout=20) as src, sqlite3.connect(target) as dst:
        src.backup(dst)
        dst.commit()
    target.chmod(0o600)


def rehearse_one(name: str, source: Path, directory: Path) -> dict:
    row = {'name': name, 'source_present': source.is_file(), 'snapshot_created': False, 'restore_created': False,
           'integrity_ok': False, 'schema_parity': False, 'page_count_parity': False, 'production_modified': False}
    if not source.is_file() or source.is_symlink():
        row['state'] = 'unavailable'
        return row
    snap = directory / f'{name}.snapshot.sqlite'
    restored = directory / f'{name}.restored.sqlite'
    try:
        before = inspect(source)
        snapshot(source, snap)
        row['snapshot_created'] = True
        snapshot_meta = inspect(snap)
        shutil.copyfile(snap, restored)
        restored.chmod(0o600)
        row['restore_created'] = True
        after = inspect(restored)
        row['integrity_ok'] = snapshot_meta['integrity'] == 'ok' and after['integrity'] == 'ok'
        row['schema_parity'] = before['tables'] == snapshot_meta['tables'] == after['tables'] and before['user_version'] == after['user_version']
        row['page_count_parity'] = snapshot_meta['pages'] == after['pages']
        row['state'] = 'passed' if row['integrity_ok'] and row['schema_parity'] and row['page_count_parity'] else 'failed'
        row['tables'] = after['tables']
        row['user_version'] = after['user_version']
    except (sqlite3.Error, OSError) as exc:
        row['state'] = 'failed'
        row['error_type'] = type(exc).__name__
    return row


def build() -> dict:
    WORK_ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(WORK_ROOT, 0o700)
    with tempfile.TemporaryDirectory(prefix='run-', dir=WORK_ROOT) as temporary:
        directory = Path(temporary)
        rows = [rehearse_one(name, path, directory) for name, path in DATABASES.items()]
    # TemporaryDirectory removal is part of acceptance: database contents must not persist here.
    residual = [p.name for p in WORK_ROOT.iterdir() if p.is_file()]
    passed = sum(1 for row in rows if row.get('state') == 'passed')
    failed = sum(1 for row in rows if row.get('state') == 'failed')
    unavailable = sum(1 for row in rows if row.get('state') == 'unavailable')
    state = 'healthy' if failed == 0 and unavailable == 0 and passed == len(DATABASES) and not residual else 'attention'
    return {
        'contract': 'wwcx.general-recovery-rehearsal.v1',
        'generated_at': utcnow(),
        'state': state,
        'databases': rows,
        'summary': {'configured': len(DATABASES), 'passed': passed, 'failed': failed, 'unavailable': unavailable},
        'disposable_artifacts_remaining': len(residual),
        'production_restore_performed': False,
        'production_modified': False,
        'secrets_exposed': False,
    }


def main() -> int:
    data = build()
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(json.dumps(data, indent=2) + '\n')
    STATUS.chmod(0o644)
    print(json.dumps({'state': data['state'], **data['summary'], 'residual': data['disposable_artifacts_remaining']}, sort_keys=True))
    return 0 if data['state'] == 'healthy' else 1


if __name__ == '__main__':
    raise SystemExit(main())
