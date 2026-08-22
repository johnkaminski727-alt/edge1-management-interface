#!/usr/bin/env python3
"""Backup + isolated restore acceptance for the private WW.CX Digital Archive.

Paperless uses its document_exporter/document_importer path. ArchiveBox uses a
full data-directory snapshot and a network-disabled ``archivebox status``
restore check. Backup and restore evidence is retained. No public route or
canonical source is changed.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import secrets
import shutil
import subprocess
import sys
import tarfile
import time
from typing import Any

EXPECTED_REPO = Path('/opt/edge1-management-interface')
RUNTIME_ROOT = Path('/var/lib/wwcx-digital-archive')
BACKUP_ROOT = RUNTIME_ROOT / 'backups'
RESTORE_ROOT = RUNTIME_ROOT / 'restore-tests'
PAPERLESS_EXPORT_ROOT = RUNTIME_ROOT / 'paperless/export'
PAPERLESS_CONSUME_ROOT = RUNTIME_ROOT / 'paperless/consume'
ARCHIVEBOX_DATA_ROOT = RUNTIME_ROOT / 'archivebox/data'
PAPERLESS_COMPOSE = Path('deploy/digital-archive/paperless/compose.yaml')
ARCHIVEBOX_COMPOSE = Path('deploy/digital-archive/archivebox/compose.yaml')
PAPERLESS_PROJECT = 'wwcx-paperless'
ARCHIVEBOX_PROJECT = 'wwcx-archivebox'
PAPERLESS_IMAGE = 'ghcr.io/paperless-ngx/paperless-ngx:3.0.5'
POSTGRES_IMAGE = 'postgres:17-alpine'
VALKEY_IMAGE = 'valkey/valkey:8-alpine'
ARCHIVEBOX_IMAGE = 'archivebox/archivebox:0.7.4'
MANIFEST_SCHEMA = 'wwcx.digital-archive.backup-set.v1'
RESTORE_SCHEMA = 'wwcx.digital-archive.restore-acceptance.v1'


class BackupError(RuntimeError):
    pass


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def run(command: list[str], *, env: dict[str, str] | None = None, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    safe_env = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8'}
    if env:
        safe_env.update(env)
    try:
        return subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=safe_env,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise BackupError(f'command unavailable: {Path(command[0]).name}: {type(exc).__name__}') from exc


def require_success(command: list[str], *, env: dict[str, str] | None = None, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    result = run(command, env=env, timeout=timeout)
    if result.returncode != 0:
        raise BackupError(f'command failed: {Path(command[0]).name} exit={result.returncode}')
    return result


def docker_ready() -> bool:
    docker = shutil.which('docker')
    return bool(docker and run([docker, 'compose', 'version'], timeout=20).returncode == 0)


def compose_command(repo: Path, project: str, relative: Path, *args: str) -> list[str]:
    return [
        shutil.which('docker') or '/usr/bin/docker', 'compose',
        '--project-name', project, '--file', str(repo / relative), *args,
    ]


def project_running(repo: Path, project: str, relative: Path, env: dict[str, str]) -> bool:
    result = run(compose_command(repo, project, relative, 'ps', '--status', 'running', '--services'), env=env, timeout=30)
    return result.returncode == 0 and bool(result.stdout.strip())


def secret_env(db_password_file: Path, secret_key_file: Path) -> dict[str, str]:
    return {
        'PAPERLESS_DB_PASSWORD_FILE': str(db_password_file.expanduser().resolve()),
        'PAPERLESS_SECRET_KEY_FILE': str(secret_key_file.expanduser().resolve()),
    }


def validate_secret(path: Path) -> None:
    path = path.expanduser()
    if path.is_symlink() or not path.is_file():
        raise BackupError('Paperless runtime secret path is missing, symlinked, or not a file')
    if path.stat().st_mode & 0o077:
        raise BackupError('Paperless runtime secret permissions are too broad')


def consume_queue_empty(path: Path = PAPERLESS_CONSUME_ROOT) -> bool:
    if path.is_symlink() or not path.is_dir():
        return False
    try:
        return next(path.iterdir(), None) is None
    except OSError:
        return False


def require_consume_quiescent(path: Path = PAPERLESS_CONSUME_ROOT) -> None:
    if not consume_queue_empty(path):
        raise BackupError('Paperless consume queue must be empty before backup')


def preflight(repo: Path, db_password_file: Path | None = None, secret_key_file: Path | None = None) -> dict[str, Any]:
    repo = repo.expanduser().resolve()
    blockers = []
    if not repo.is_dir():
        blockers.append('repository-missing')
    if not docker_ready():
        blockers.append('docker-compose-unavailable')
    if not PAPERLESS_EXPORT_ROOT.is_dir():
        blockers.append('paperless-export-root-missing')
    if not PAPERLESS_CONSUME_ROOT.is_dir() or PAPERLESS_CONSUME_ROOT.is_symlink():
        blockers.append('paperless-consume-root-missing-or-unsafe')
    elif not consume_queue_empty(PAPERLESS_CONSUME_ROOT):
        blockers.append('paperless-consume-queue-not-empty')
    if not ARCHIVEBOX_DATA_ROOT.is_dir():
        blockers.append('archivebox-data-root-missing')
    if db_password_file is None or secret_key_file is None:
        blockers.append('paperless-secret-paths-not-specified')
    else:
        try:
            validate_secret(db_password_file)
            validate_secret(secret_key_file)
        except BackupError as exc:
            blockers.append(str(exc))
    return {
        'status': 'preflight-ok' if not blockers else 'preflight-blocked',
        'repo': str(repo),
        'backup_root': str(BACKUP_ROOT),
        'restore_root': str(RESTORE_ROOT),
        'paperless_image': PAPERLESS_IMAGE,
        'archivebox_image': ARCHIVEBOX_IMAGE,
        'paperless_consume_queue_empty': 'paperless-consume-queue-not-empty' not in blockers and 'paperless-consume-root-missing-or-unsafe' not in blockers,
        'public_changes': False,
        'canonical_source_changes': False,
        'deletes_backup_data': False,
        'off_host_backup_created': False,
        'blockers': blockers,
    }


def tar_directory(source: Path, target: Path) -> None:
    if source.is_symlink() or not source.is_dir():
        raise BackupError(f'backup source is not a regular directory: {source}')
    target.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(target, 'w:gz') as archive:
        archive.dereference = False
        for child in sorted(source.iterdir(), key=lambda path: path.name):
            archive.add(child, arcname=child.name, recursive=True)


def _safe_member(member: tarfile.TarInfo) -> bool:
    name = PurePosixPath(member.name)
    if name.is_absolute() or '..' in name.parts:
        return False
    if member.issym() or member.islnk():
        link = PurePosixPath(member.linkname)
        if link.is_absolute():
            return False
        combined = name.parent.joinpath(link)
        depth = 0
        for part in combined.parts:
            if part == '..':
                depth -= 1
            elif part not in ('', '.'):
                depth += 1
            if depth < 0:
                return False
    return True


def safe_extract(archive_path: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    with tarfile.open(archive_path, 'r:gz') as archive:
        members = archive.getmembers()
        if any(not _safe_member(member) for member in members):
            raise BackupError('backup archive contains an unsafe path or link')
        archive.extractall(destination, members=members)


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f'.{path.name}.tmp-{os.getpid()}')
    temp.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    os.chmod(temp, 0o600)
    os.replace(temp, path)


def snapshot(repo: Path, db_password_file: Path, secret_key_file: Path) -> dict[str, Any]:
    if os.geteuid() != 0:
        raise BackupError('--snapshot requires root')
    repo = repo.expanduser().resolve()
    if repo != EXPECTED_REPO:
        raise BackupError('snapshot is restricted to the canonical Edge1 repository')
    info = preflight(repo, db_password_file, secret_key_file)
    if info['blockers']:
        raise BackupError('preflight blocked: ' + ', '.join(info['blockers']))
    env = secret_env(db_password_file, secret_key_file)
    if not project_running(repo, PAPERLESS_PROJECT, PAPERLESS_COMPOSE, env):
        raise BackupError('Paperless project is not running')
    archivebox_running = project_running(repo, ARCHIVEBOX_PROJECT, ARCHIVEBOX_COMPOSE, env)
    stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup_id = f'backup-{stamp}-{os.getpid()}'
    backup_dir = BACKUP_ROOT / backup_id
    backup_dir.mkdir(parents=True, exist_ok=False)
    os.chmod(backup_dir, 0o700)

    require_consume_quiescent()
    export_dir = PAPERLESS_EXPORT_ROOT / backup_id
    if export_dir.exists():
        raise BackupError('Paperless export destination already exists')
    exporter = compose_command(
        repo, PAPERLESS_PROJECT, PAPERLESS_COMPOSE,
        'exec', '-T', 'webserver', 'document_exporter', f'../export/{backup_id}', '--no-progress-bar',
    )
    require_success(exporter, env=env, timeout=1800)
    require_consume_quiescent()
    paperless_tar = backup_dir / 'paperless-export.tar.gz'
    tar_directory(export_dir, paperless_tar)

    archivebox_tar = backup_dir / 'archivebox-data.tar.gz'
    stopped = False
    try:
        if archivebox_running:
            require_success(compose_command(repo, ARCHIVEBOX_PROJECT, ARCHIVEBOX_COMPOSE, 'stop', 'archivebox'), env=env, timeout=120)
            stopped = True
        tar_directory(ARCHIVEBOX_DATA_ROOT, archivebox_tar)
    finally:
        if stopped:
            restart = run(compose_command(repo, ARCHIVEBOX_PROJECT, ARCHIVEBOX_COMPOSE, 'start', 'archivebox'), env=env, timeout=120)
            if restart.returncode != 0 and sys.exc_info()[0] is None:
                raise BackupError('ArchiveBox restart failed after backup snapshot')

    manifest = {
        'schema': MANIFEST_SCHEMA,
        'backup_id': backup_id,
        'created_at': utc_now(),
        'paperless_image': PAPERLESS_IMAGE,
        'archivebox_image': ARCHIVEBOX_IMAGE,
        'files': {
            'paperless-export.tar.gz': {'sha256': sha256_file(paperless_tar), 'bytes': paperless_tar.stat().st_size},
            'archivebox-data.tar.gz': {'sha256': sha256_file(archivebox_tar), 'bytes': archivebox_tar.stat().st_size},
        },
        'paperless_export_path_recorded': False,
        'paperless_consume_queue_empty': True,
        'secret_values_recorded': False,
        'archivebox_was_running': archivebox_running,
        'archivebox_temporarily_stopped': archivebox_running,
        'public_changes': False,
        'canonical_source_changes': False,
        'off_host_backup_created': False,
    }
    atomic_json(backup_dir / 'manifest.json', manifest)
    return {'status': 'backup-created', 'backup': str(backup_dir), 'backup_id': backup_id, 'public_changes': False}


def load_manifest(backup_dir: Path) -> dict[str, Any]:
    backup_dir = backup_dir.expanduser().resolve()
    try:
        manifest = json.loads((backup_dir / 'manifest.json').read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise BackupError('backup manifest is invalid') from exc
    if manifest.get('schema') != MANIFEST_SCHEMA:
        raise BackupError('unsupported backup manifest')
    for name in ('paperless-export.tar.gz', 'archivebox-data.tar.gz'):
        path = backup_dir / name
        entry = manifest.get('files', {}).get(name, {})
        if not path.is_file() or path.is_symlink() or sha256_file(path) != entry.get('sha256'):
            raise BackupError(f'backup hash verification failed: {name}')
    return manifest


def restore_compose_text(root: Path) -> str:
    return f'''services:\n  db:\n    image: {POSTGRES_IMAGE}\n    environment:\n      POSTGRES_DB: paperless\n      POSTGRES_USER: paperless\n      POSTGRES_PASSWORD: ${{RESTORE_DB_PASSWORD}}\n    volumes:\n      - {root / 'postgres'}:/var/lib/postgresql/data\n    networks: [restore]\n  broker:\n    image: {VALKEY_IMAGE}\n    volumes:\n      - {root / 'valkey'}:/data\n    networks: [restore]\n  webserver:\n    image: {PAPERLESS_IMAGE}\n    depends_on:\n      - db\n      - broker\n    environment:\n      PAPERLESS_REDIS: redis://broker:6379\n      PAPERLESS_DBHOST: db\n      PAPERLESS_DBNAME: paperless\n      PAPERLESS_DBUSER: paperless\n      PAPERLESS_DBPASS: ${{RESTORE_DB_PASSWORD}}\n      PAPERLESS_SECRET_KEY: ${{RESTORE_SECRET_KEY}}\n      PAPERLESS_TIME_ZONE: Atlantic/Reykjavik\n    volumes:\n      - {root / 'data'}:/usr/src/paperless/data\n      - {root / 'media'}:/usr/src/paperless/media\n      - {root / 'export'}:/usr/src/paperless/export\n      - {root / 'consume'}:/usr/src/paperless/consume\n      - {root / 'paperless-backup'}:/restore:ro\n    networks: [restore]\nnetworks:\n  restore:\n    internal: true\n'''


def wait_paperless_cli(compose: Path, project: str, env: dict[str, str], timeout: int = 180) -> None:
    deadline = time.monotonic() + timeout
    command = [
        shutil.which('docker') or '/usr/bin/docker', 'compose',
        '--project-name', project, '--file', str(compose),
        'exec', '-T', 'webserver', 'document_importer', '--help',
    ]
    while time.monotonic() < deadline:
        if run(command, env=env, timeout=30).returncode == 0:
            return
        time.sleep(3)
    raise BackupError('disposable Paperless restore target did not become ready')


def acceptance_pass(paperless_ok: bool, archivebox_ok: bool, cleanup_ok: bool) -> bool:
    return paperless_ok and archivebox_ok and cleanup_ok


def restore_check(backup_dir: Path) -> dict[str, Any]:
    if os.geteuid() != 0:
        raise BackupError('--restore-check requires root')
    if not docker_ready():
        raise BackupError('docker compose is unavailable')
    backup_dir = backup_dir.expanduser().resolve()
    try:
        backup_dir.relative_to(BACKUP_ROOT.resolve())
    except ValueError as exc:
        raise BackupError('backup directory escapes managed backup root') from exc
    manifest = load_manifest(backup_dir)
    run_root = RESTORE_ROOT / f"{manifest['backup_id']}-{os.getpid()}"
    run_root.mkdir(parents=True, exist_ok=False)
    os.chmod(run_root, 0o700)
    paperless_backup = run_root / 'paperless-backup'
    archivebox_data = run_root / 'archivebox-data'
    safe_extract(backup_dir / 'paperless-export.tar.gz', paperless_backup)
    safe_extract(backup_dir / 'archivebox-data.tar.gz', archivebox_data)
    for name in ('postgres', 'valkey', 'data', 'media', 'export', 'consume'):
        (run_root / name).mkdir()

    compose = run_root / 'paperless-restore.compose.yaml'
    compose.write_text(restore_compose_text(run_root), encoding='utf-8')
    os.chmod(compose, 0o600)
    env = {'RESTORE_DB_PASSWORD': secrets.token_hex(24), 'RESTORE_SECRET_KEY': secrets.token_hex(48)}
    project = 'wwcx-paperless-restore-' + hashlib.sha256(str(run_root).encode()).hexdigest()[:12]
    docker = shutil.which('docker') or '/usr/bin/docker'
    compose_base = [docker, 'compose', '--project-name', project, '--file', str(compose)]
    paperless_ok = False
    paperless_failure_type: str | None = None
    cleanup_ok = False
    try:
        require_success([*compose_base, 'up', '-d'], env=env, timeout=600)
        wait_paperless_cli(compose, project, env)
        require_success(
            [*compose_base, 'exec', '-T', 'webserver', 'document_importer', '/restore', '--no-progress-bar'],
            env=env,
            timeout=1800,
        )
        paperless_ok = True
    except BackupError as exc:
        paperless_failure_type = type(exc).__name__
    finally:
        cleanup = run([*compose_base, 'down'], env=env, timeout=300)
        cleanup_ok = cleanup.returncode == 0

    archivebox = run(
        [docker, 'run', '--rm', '--network', 'none', '-v', f'{archivebox_data}:/data', ARCHIVEBOX_IMAGE, 'status'],
        timeout=300,
    )
    archivebox_ok = archivebox.returncode == 0
    passed = acceptance_pass(paperless_ok, archivebox_ok, cleanup_ok)
    result = {
        'schema': RESTORE_SCHEMA,
        'checked_at': utc_now(),
        'backup_id': manifest['backup_id'],
        'paperless_import_pass': paperless_ok,
        'paperless_failure_type': paperless_failure_type,
        'archivebox_status_pass': archivebox_ok,
        'disposable_cleanup_pass': cleanup_ok,
        'result': 'pass' if passed else 'fail',
        'restore_root': str(run_root),
        'restore_state_preserved': True,
        'production_projects_changed': False,
        'restore_network_external_egress': False,
        'public_changes': False,
        'canonical_source_changes': False,
        'ephemeral_secret_values_recorded': False,
    }
    atomic_json(run_root / 'restore-acceptance.json', result)
    if not passed:
        raise BackupError(f'restore acceptance failed; evidence={run_root}')
    return result


def parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='WW.CX Digital Archive backup/restore acceptance')
    parser.add_argument('--repo', type=Path, default=EXPECTED_REPO)
    parser.add_argument('--paperless-db-password-file', type=Path)
    parser.add_argument('--paperless-secret-key-file', type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--snapshot', action='store_true')
    mode.add_argument('--restore-check', type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.restore_check is not None:
            result = restore_check(args.restore_check)
        elif args.snapshot:
            if args.paperless_db_password_file is None or args.paperless_secret_key_file is None:
                raise BackupError('--snapshot requires Paperless runtime secret-file paths')
            result = snapshot(args.repo, args.paperless_db_password_file, args.paperless_secret_key_file)
        else:
            result = preflight(args.repo, args.paperless_db_password_file, args.paperless_secret_key_file)
    except (BackupError, OSError, json.JSONDecodeError, tarfile.TarError) as exc:
        print(f'digital-archive-backup-acceptance: {exc}', file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
