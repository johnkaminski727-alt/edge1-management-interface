#!/usr/bin/env python3
"""Backup-first Edge1 foundation installer for Cookie Monster Alpha.

Default mode is read-only preflight. --apply creates only the private runtime
filesystem/user/config/unit foundation; it does not enable a dataset, start a
Fengus job, publish a web route, or change DNS/certificates/firewall/auth.

Rollback restores only configuration/unit files managed by this installer.
Runtime directories and a newly-created service account are intentionally
preserved so rollback cannot destroy staged/evidence data or invalidate UIDs.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess
import sys
from typing import Any

EXPECTED_REPO = Path('/opt/edge1-management-interface')
REGISTRY_SOURCE = Path('config/cookie-monster/datasets.example.json')
UNIT_SOURCE = Path('deploy/cookie-monster-fengus-worker@.service')
REGISTRY_DEST = Path('/etc/wwcx-cookie-monster/datasets.json')
UNIT_DEST = Path('/etc/systemd/system/cookie-monster-fengus-worker@.service')
DATASET_ROOT = Path('/srv/cookie-monster/datasets')
STAGING_DATASET = DATASET_ROOT / 'alpha-staging'
RUNTIME_ROOT = Path('/var/lib/cookie-monster-alpha')
GENERATED_ROOT = RUNTIME_ROOT / 'generated'
FENGUS_ROOT = RUNTIME_ROOT / 'fengus'
FENGUS_INBOX = FENGUS_ROOT / 'inbox'
FENGUS_OUTBOX = FENGUS_ROOT / 'outbox'
BACKUP_ROOT = Path('/var/backups')
FENGUS_USER = 'cookie-monster-fengus'
FENGUS_GROUP = 'cookie-monster-fengus'
STATE_SCHEMA = 'wwcx.cookie-monster.edge1-foundation-install.v1'


class InstallError(RuntimeError):
    pass


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise InstallError(f'command unavailable: {command[0]}: {type(exc).__name__}') from exc


def load_registry(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise InstallError(f'invalid registry source: {exc}') from exc
    datasets = value.get('datasets') if isinstance(value, dict) else None
    entry = datasets.get('alpha-staging') if isinstance(datasets, dict) else None
    if value.get('schema') != 'wwcx.cookie-monster.datasets.v1' or not isinstance(entry, dict):
        raise InstallError('registry source missing expected alpha-staging entry')
    if entry.get('enabled') is not False or entry.get('non_production') is not True or entry.get('read_only') is not True:
        raise InstallError('registry source must keep alpha-staging disabled, non-production and read-only')
    forbidden = {'path', 'url', 'uri', 'command', 'credential', 'secret', 'password', 'token'}
    if forbidden.intersection(entry):
        raise InstallError('registry source contains forbidden authority-bearing fields')
    return value


def source_paths(repo: Path) -> tuple[Path, Path]:
    return repo / REGISTRY_SOURCE, repo / UNIT_SOURCE


def preflight(repo: Path = EXPECTED_REPO) -> dict[str, Any]:
    repo = repo.expanduser().resolve()
    registry, unit = source_paths(repo)
    if not repo.is_dir():
        raise InstallError(f'repository missing: {repo}')
    if not registry.is_file():
        raise InstallError(f'registry source missing: {registry}')
    if not unit.is_file():
        raise InstallError(f'worker unit source missing: {unit}')
    load_registry(registry)
    unit_text = unit.read_text(encoding='utf-8')
    required = (
        'PrivateNetwork=yes',
        'ProtectSystem=strict',
        'InaccessiblePaths=/srv/cookie-monster',
        'User=cookie-monster-fengus',
    )
    missing = [item for item in required if item not in unit_text]
    if missing:
        raise InstallError('worker unit missing hardening: ' + ', '.join(missing))
    user_exists = True
    try:
        pwd.getpwnam(FENGUS_USER)
    except KeyError:
        user_exists = False
    registry_conflict = REGISTRY_DEST.is_file() and REGISTRY_DEST.read_bytes() != registry.read_bytes()
    return {
        'status': 'preflight-ok',
        'repo': str(repo),
        'user_exists': user_exists,
        'registry_destination': str(REGISTRY_DEST),
        'registry_conflict': registry_conflict,
        'worker_unit_destination': str(UNIT_DEST),
        'dataset': str(STAGING_DATASET),
        'generated_root': str(GENERATED_ROOT),
        'fengus_inbox': str(FENGUS_INBOX),
        'fengus_outbox': str(FENGUS_OUTBOX),
        'dataset_enabled': False,
        'starts_worker': False,
        'public_changes': False,
    }


def backup_file(source: Path, backup_dir: Path, name: str) -> dict[str, Any]:
    state: dict[str, Any] = {'present': source.is_file()}
    if source.is_file():
        target = backup_dir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        state['sha256'] = sha256_file(target)
    return state


def ensure_dir(path: Path, mode: int, uid: int = 0, gid: int = 0) -> bool:
    created = not path.exists()
    path.mkdir(parents=True, exist_ok=True)
    if created:
        os.chown(path, uid, gid)
        os.chmod(path, mode)
    return created


def ensure_user() -> tuple[int, int, bool]:
    try:
        entry = pwd.getpwnam(FENGUS_USER)
        return entry.pw_uid, entry.pw_gid, False
    except KeyError:
        pass
    group = run(['/usr/sbin/groupadd', '--system', FENGUS_GROUP])
    if group.returncode != 0 and 'already exists' not in group.stderr.lower():
        raise InstallError('failed to create Fengus group')
    user = run([
        '/usr/sbin/useradd', '--system', '--gid', FENGUS_GROUP,
        '--home-dir', '/nonexistent', '--shell', '/usr/sbin/nologin', FENGUS_USER,
    ])
    if user.returncode != 0:
        raise InstallError('failed to create Fengus user')
    entry = pwd.getpwnam(FENGUS_USER)
    return entry.pw_uid, entry.pw_gid, True


def apply(repo: Path = EXPECTED_REPO, backup_root: Path = BACKUP_ROOT) -> dict[str, Any]:
    if os.geteuid() != 0:
        raise InstallError('--apply requires root')
    info = preflight(repo)
    if info['registry_conflict']:
        raise InstallError('existing dataset registry differs from the disabled source example; preserve and review it instead of overwriting')
    repo = Path(info['repo'])
    registry_src, unit_src = source_paths(repo)
    stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup = backup_root / f'wwcx-cookie-monster-alpha-foundation-{stamp}-{os.getpid()}'
    backup.mkdir(parents=True, exist_ok=False)
    managed_dirs = (DATASET_ROOT, STAGING_DATASET, RUNTIME_ROOT, GENERATED_ROOT, FENGUS_ROOT, FENGUS_INBOX, FENGUS_OUTBOX)
    state: dict[str, Any] = {
        'schema': STATE_SCHEMA,
        'created_at': utc_now(),
        'files': {
            'registry': backup_file(REGISTRY_DEST, backup, 'datasets.json'),
            'unit': backup_file(UNIT_DEST, backup, 'cookie-monster-fengus-worker@.service'),
        },
        'directories_preexisting': {str(path): path.exists() for path in managed_dirs},
        'user_created': False,
    }
    (backup / 'install-state.json').write_text(json.dumps(state, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    uid, gid, user_created = ensure_user()
    state['user_created'] = user_created
    ensure_dir(DATASET_ROOT, 0o755)
    ensure_dir(STAGING_DATASET, 0o555)
    ensure_dir(RUNTIME_ROOT, 0o750)
    ensure_dir(GENERATED_ROOT, 0o750)
    ensure_dir(FENGUS_ROOT, 0o750, 0, gid)
    ensure_dir(FENGUS_INBOX, 0o750, 0, gid)
    ensure_dir(FENGUS_OUTBOX, 0o750, uid, gid)
    REGISTRY_DEST.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(registry_src, REGISTRY_DEST)
    os.chown(REGISTRY_DEST, 0, 0)
    os.chmod(REGISTRY_DEST, 0o640)
    shutil.copyfile(unit_src, UNIT_DEST)
    os.chown(UNIT_DEST, 0, 0)
    os.chmod(UNIT_DEST, 0o644)
    reload_result = run(['/bin/systemctl', 'daemon-reload'])
    if reload_result.returncode != 0:
        raise InstallError('systemctl daemon-reload failed')
    (backup / 'install-state.json').write_text(json.dumps(state, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return {
        'status': 'installed-foundation',
        'backup': str(backup),
        'dataset_enabled': False,
        'worker_started': False,
        'user_created': user_created,
    }


def restore_file(backup: Path, state: dict[str, Any], key: str, backup_name: str, destination: Path) -> None:
    item = state['files'][key]
    if item['present'] is True:
        source = backup / backup_name
        if not source.is_file():
            raise InstallError(f'backup payload missing: {source}')
        if item.get('sha256') and sha256_file(source) != item['sha256']:
            raise InstallError(f'backup hash mismatch: {source}')
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    elif destination.exists():
        destination.unlink()


def rollback(backup: Path) -> dict[str, Any]:
    if os.geteuid() != 0:
        raise InstallError('--rollback requires root')
    backup = backup.expanduser().resolve()
    try:
        state = json.loads((backup / 'install-state.json').read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise InstallError(f'invalid install-state backup: {exc}') from exc
    if state.get('schema') != STATE_SCHEMA or not isinstance(state.get('files'), dict):
        raise InstallError('unsupported install-state backup')
    restore_file(backup, state, 'registry', 'datasets.json', REGISTRY_DEST)
    restore_file(backup, state, 'unit', 'cookie-monster-fengus-worker@.service', UNIT_DEST)
    reload_result = run(['/bin/systemctl', 'daemon-reload'])
    if reload_result.returncode != 0:
        raise InstallError('systemctl daemon-reload failed after rollback')
    return {
        'status': 'rolled-back-config',
        'backup': str(backup),
        'runtime_directories_preserved': True,
        'service_account_preserved': True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Cookie Monster Edge1 foundation installer')
    parser.add_argument('--repo', type=Path, default=EXPECTED_REPO)
    parser.add_argument('--backup-root', type=Path, default=BACKUP_ROOT)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--apply', action='store_true')
    mode.add_argument('--rollback', type=Path)
    args = parser.parse_args(argv)
    try:
        if args.rollback is not None:
            result = rollback(args.rollback)
        elif args.apply:
            result = apply(args.repo, args.backup_root)
        else:
            result = preflight(args.repo)
    except InstallError as exc:
        print(f'cookie-monster-edge1-install: {exc}', file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
