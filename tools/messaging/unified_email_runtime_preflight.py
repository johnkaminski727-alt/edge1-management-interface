#!/usr/bin/env python3
"""Read-only, sanitized post-rebuild inventory; never fetches mail or credentials."""
from __future__ import annotations
import json
import socket
import sqlite3
import subprocess
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[2]
DB = Path('/var/lib/wwcx-mail-room/correspondence.sqlite3')


def command(args: list[str]) -> str | None:
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=8, check=False)
        return result.stdout.strip() if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def main() -> None:
    services = {}
    for name in ('postfix', 'wwcx-outbound-mail-gateway', 'wwcx-ava-office',
                 'bigbird-ai-gateway', 'edge1-operations-api', 'edge1-security-auth'):
        services[name] = command(['systemctl', 'show', name + '.service', '--property=ActiveState', '--value']) or 'unavailable'
    store = {'state': 'unavailable'}
    try:
        safe = DB.is_file() and not DB.is_symlink() and not DB.parent.is_symlink()
        safe = safe and not (DB.stat().st_mode & 0o077) and not (DB.parent.stat().st_mode & 0o077)
        if safe:
            with sqlite3.connect('file:' + quote(str(DB), safe='/') + '?mode=ro', uri=True) as conn:
                conn.execute('PRAGMA query_only=ON')
                rows = conn.execute('SELECT source_scope, source_authoritative, COUNT(*) FROM correspondence GROUP BY source_scope, source_authoritative').fetchall()
            store = {'state': 'readable', 'groups': [{'scope': str(r[0]) if str(r[0]) in {'local_native', 'production_native', 'synthetic', 'legacy_unscoped'} else 'unknown', 'authoritative': bool(r[1]), 'count': r[2]} for r in rows]}
        elif DB.exists():
            store = {'state': 'unsafe_permissions_or_symlink'}
    except (OSError, sqlite3.Error):
        store = {'state': 'permission_or_schema_check_required'}
    host = socket.getfqdn()
    dirty = command(["git", "-C", str(ROOT), "status", "--porcelain"])
    print(json.dumps({
        'contract': 'wwcx.unified-email-runtime-preflight.v1',
        'target_is_edge1': host in {'edge1', 'edge1.ww.cx'},
        'repository_head': command(['git', '-C', str(ROOT), 'rev-parse', 'HEAD']),
        'repository_dirty': bool(dirty) if dirty is not None else None,
        'services': services, 'correspondence_store': store,
        'postfix': {key: command(['postconf', '-h', key]) for key in ('inet_interfaces', 'virtual_mailbox_domains', 'virtual_transport')},
        'mailbox_login_attempted': False, 'mail_fetched': False,
        'production_modified': False,
        'note': 'Aggregate inventory only; not acceptance of delivery, scanning, DNS or AVA runtime attachment.',
    }, indent=2))

if __name__ == '__main__':
    main()
