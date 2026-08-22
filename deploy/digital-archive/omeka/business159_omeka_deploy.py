#!/usr/bin/env python3
"""Bounded Omeka S 4.2 private deployment transaction for Business159."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
from typing import Any

APP_ROOT_DEFAULT = Path('~/apps/wwcx-omeka-s')
STATE_SCHEMA = 'wwcx.digital-archive.omeka-business159.v1'
REQUIRED_PHP_EXTENSIONS = {'PDO', 'pdo_mysql', 'mbstring', 'xml'}
MAX_PAYLOAD_BYTES = 512 * 1024 * 1024


class OmekaDeployError(RuntimeError):
    pass


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def run(command: list[str], timeout: int = 30) -> subprocess.CompletedProcess[str]:
    env = {'PATH': os.environ.get('PATH', '/usr/local/bin:/usr/bin:/bin'), 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8'}
    try:
        return subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise OmekaDeployError(f'command unavailable: {Path(command[0]).name}: {type(exc).__name__}') from exc


def php_status() -> dict[str, Any]:
    php = shutil.which('php')
    if not php:
        return {'ready': False, 'reason': 'php-cli-unavailable'}
    version = run([php, '-r', 'echo PHP_VERSION;'])
    modules = run([php, '-m'])
    if version.returncode != 0 or modules.returncode != 0:
        return {'ready': False, 'reason': 'php-cli-check-failed'}
    module_set = {line.strip() for line in modules.stdout.splitlines() if line.strip()}
    missing = sorted(REQUIRED_PHP_EXTENSIONS - module_set)
    match = re.match(r'^(\d+)\.(\d+)\.', version.stdout.strip())
    if not match:
        return {'ready': False, 'reason': 'php-version-unparseable'}
    php_tuple = (int(match.group(1)), int(match.group(2)))
    return {'ready': php_tuple >= (8, 1) and not missing, 'version': version.stdout.strip(), 'missing_extensions': missing, 'php_path': php}


def thumbnail_status() -> dict[str, Any]:
    php = shutil.which('php')
    imagick = gd = False
    if php:
        result = run([php, '-r', 'echo extension_loaded("imagick") ? "yes" : "no";'])
        imagick = result.returncode == 0 and result.stdout.strip() == 'yes'
        result = run([php, '-r', 'echo extension_loaded("gd") ? "yes" : "no";'])
        gd = result.returncode == 0 and result.stdout.strip() == 'yes'
    imagemagick = shutil.which('magick') or shutil.which('convert')
    return {'ready': bool(imagick or imagemagick or gd), 'imagick': imagick, 'imagemagick_cli': bool(imagemagick), 'gd': gd}


def apache_rewrite_evidence(app_root: Path) -> dict[str, Any]:
    parent = app_root.parent
    return {'verified': False, 'reason': 'shared-host-vhost-policy-must-be-verified-by-browser-or-control-plane', 'parent_writable': parent.exists() and os.access(parent, os.W_OK)}


def database_ini_status(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {'ready': False, 'reason': 'not-specified'}
    path = path.expanduser()
    if path.is_symlink():
        return {'ready': False, 'reason': 'symlink-rejected'}
    try:
        info = path.stat()
    except OSError:
        return {'ready': False, 'reason': 'missing-or-unreadable'}
    if not stat.S_ISREG(info.st_mode):
        return {'ready': False, 'reason': 'not-regular-file'}
    mode = stat.S_IMODE(info.st_mode)
    if mode & 0o077:
        return {'ready': False, 'reason': 'permissions-too-broad', 'mode': oct(mode)}
    try:
        text = path.read_text(encoding='utf-8')
    except OSError:
        return {'ready': False, 'reason': 'unreadable'}
    required = ('user', 'password', 'dbname', 'host')
    missing = [key for key in required if not re.search(rf'(?m)^\s*{key}\s*=\s*.+$', text)]
    if missing:
        return {'ready': False, 'reason': 'missing-required-settings', 'missing': missing}
    return {'ready': True, 'reason': 'ready', 'mode': oct(mode), 'bytes': info.st_size}


def normalize_sha(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.lower().strip()
    if value.startswith('sha256:'):
        value = value.split(':', 1)[1]
    if not re.fullmatch(r'[a-f0-9]{64}', value):
        raise OmekaDeployError('expected tree SHA-256 must be 64 lowercase hex characters')
    return value


def payload_status(payload: Path | None, expected_tree_sha256: str | None) -> dict[str, Any]:
    if payload is None:
        return {'ready': False, 'reason': 'payload-not-specified'}
    payload = payload.expanduser().resolve()
    if payload.is_symlink() or not payload.is_dir():
        return {'ready': False, 'reason': 'payload-missing-or-not-directory'}
    required = ('application', 'config', 'files', 'modules', 'themes', 'index.php')
    missing = [name for name in required if not (payload / name).exists()]
    if missing:
        return {'ready': False, 'reason': 'payload-structure-invalid', 'missing': missing}
    version_text = ''
    for candidate in (payload / 'VERSION', payload / 'application/config/module.config.php'):
        if candidate.is_file() and not candidate.is_symlink():
            try:
                version_text += candidate.read_text(encoding='utf-8', errors='ignore')[:200000]
            except OSError:
                pass
    match = re.search(r'(?<!\d)(4\.2(?:\.\d+)?)(?!\d)', version_text)
    if not match:
        return {'ready': False, 'reason': 'omeka-4.2-version-not-verifiable'}
    total = count = 0
    digest = hashlib.sha256()
    for path in sorted(payload.rglob('*')):
        if path.is_symlink():
            return {'ready': False, 'reason': 'payload-symlink-rejected'}
        if not path.is_file():
            continue
        rel = path.relative_to(payload).as_posix()
        size = path.stat().st_size
        total += size
        count += 1
        if total > MAX_PAYLOAD_BYTES:
            return {'ready': False, 'reason': 'payload-too-large'}
        file_hash = sha256_file(path)
        digest.update(rel.encode() + b'\0' + file_hash.encode('ascii') + b'\n')
    tree_hash = digest.hexdigest()
    expected = normalize_sha(expected_tree_sha256)
    if expected is not None and tree_hash != expected:
        return {'ready': False, 'reason': 'payload-sha256-mismatch', 'tree_sha256': tree_hash}
    return {'ready': True, 'reason': 'ready', 'version': match.group(1), 'tree_sha256': tree_hash, 'files': count, 'bytes': total}


def disk_status(root: Path) -> dict[str, Any]:
    probe = root.expanduser()
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    usage = shutil.disk_usage(probe)
    minimum = 1024 * 1024 * 1024
    return {'ready': usage.free >= minimum, 'free_bytes': usage.free, 'minimum_free_bytes': minimum}


def preflight(app_root: Path = APP_ROOT_DEFAULT, payload: Path | None = None, expected_tree_sha256: str | None = None, database_ini: Path | None = None) -> dict[str, Any]:
    app_root = app_root.expanduser().resolve()
    php = php_status()
    thumbs = thumbnail_status()
    db = database_ini_status(database_ini)
    release = payload_status(payload, expected_tree_sha256)
    disk = disk_status(app_root)
    rewrite = apache_rewrite_evidence(app_root)
    current = app_root / 'current'
    shared_db = app_root / 'shared/config/database.ini'
    blockers = []
    if not php.get('ready'):
        blockers.append('php-requirements-not-ready')
    if not thumbs.get('ready'):
        blockers.append('thumbnail-backend-not-ready')
    if not db.get('ready'):
        blockers.append('database-ini-' + db.get('reason', 'not-ready'))
    if not release.get('ready'):
        blockers.append('release-' + release.get('reason', 'not-ready'))
    if not disk.get('ready'):
        blockers.append('insufficient-free-storage')
    if current.exists() and not current.is_symlink():
        blockers.append('current-path-conflict')
    if shared_db.exists() and database_ini is not None and shared_db.read_bytes() != database_ini.expanduser().read_bytes():
        blockers.append('shared-database-ini-conflict')
    return {
        'status': 'preflight-ok' if not blockers else 'preflight-blocked',
        'app_root': str(app_root),
        'php': php,
        'thumbnail_backend': thumbs,
        'database_ini': db,
        'release': release,
        'disk': disk,
        'apache_rewrite': rewrite,
        'public_route_verified': False,
        'public_changes': False,
        'creates_database': False,
        'creates_first_admin': False,
        'persistent_files_root': str(app_root / 'shared/files'),
        'blockers': blockers,
    }


def atomic_json(path: Path, value: dict[str, Any], mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f'.{path.name}.tmp-{os.getpid()}')
    temp.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    os.chmod(temp, mode)
    os.replace(temp, path)


def copy_payload(source: Path, destination: Path) -> None:
    if destination.exists():
        raise OmekaDeployError('release destination already exists')
    shutil.copytree(source, destination, symlinks=False)
    if any(path.is_symlink() for path in destination.rglob('*')):
        raise OmekaDeployError('copied release unexpectedly contains symlink')


def install_shared_runtime(app_root: Path, release_dir: Path, database_ini: Path) -> None:
    shared_files = app_root / 'shared/files'
    shared_config = app_root / 'shared/config'
    shared_files.mkdir(parents=True, exist_ok=True)
    shared_config.mkdir(parents=True, exist_ok=True)
    os.chmod(shared_files, 0o750)
    os.chmod(shared_config, 0o700)
    shared_db = shared_config / 'database.ini'
    if shared_db.exists():
        if shared_db.is_symlink() or not shared_db.is_file() or shared_db.read_bytes() != database_ini.read_bytes():
            raise OmekaDeployError('shared database.ini conflicts with supplied runtime configuration')
    else:
        shutil.copyfile(database_ini, shared_db)
        os.chmod(shared_db, 0o600)
    release_files = release_dir / 'files'
    if release_files.exists():
        if release_files.is_symlink() or not release_files.is_dir() or any(release_files.iterdir()):
            raise OmekaDeployError('release files directory must be an empty regular directory before shared-data linkage')
        release_files.rmdir()
    release_files.symlink_to(shared_files, target_is_directory=True)
    release_db = release_dir / 'config/database.ini'
    if release_db.exists() and not release_db.is_symlink():
        release_db.unlink()
    release_db.symlink_to(shared_db)


def apply(app_root: Path, payload: Path, expected_tree_sha256: str, database_ini: Path) -> dict[str, Any]:
    info = preflight(app_root, payload, expected_tree_sha256, database_ini)
    if info['blockers']:
        raise OmekaDeployError('preflight blocked: ' + ', '.join(info['blockers']))
    app_root = app_root.expanduser().resolve()
    payload = payload.expanduser().resolve()
    database_ini = database_ini.expanduser().resolve()
    app_root.mkdir(parents=True, exist_ok=True)
    releases = app_root / 'releases'
    evidence_root = app_root / 'evidence'
    releases.mkdir(mode=0o750, exist_ok=True)
    evidence_root.mkdir(mode=0o700, exist_ok=True)
    tree_hash = info['release']['tree_sha256']
    stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    release_dir = releases / f'{tree_hash[:16]}-{stamp}-{os.getpid()}'
    copy_payload(payload, release_dir)
    install_shared_runtime(app_root, release_dir, database_ini)
    current = app_root / 'current'
    prior_target = os.readlink(current) if current.is_symlink() else None
    temp_link = app_root / f'.current.tmp-{os.getpid()}'
    try:
        temp_link.symlink_to(release_dir)
        os.replace(temp_link, current)
    finally:
        if temp_link.exists() or temp_link.is_symlink():
            temp_link.unlink()
    evidence = evidence_root / f'{stamp}-{os.getpid()}'
    evidence.mkdir(mode=0o700)
    state = {
        'schema': STATE_SCHEMA,
        'deployed_at': utc_now(),
        'release_tree_sha256': tree_hash,
        'release_dir': str(release_dir),
        'prior_current_target': prior_target,
        'current_target': str(release_dir),
        'persistent_files_root': str(app_root / 'shared/files'),
        'database_ini_shared': True,
        'database_ini_values_recorded': False,
        'public_changes': False,
        'database_created': False,
        'first_admin_created': False,
    }
    atomic_json(evidence / 'deployment-state.json', state)
    atomic_json(app_root / 'current-deployment.json', {'schema': STATE_SCHEMA, 'evidence': str(evidence)})
    return {'status': 'private-files-deployed', 'release_tree_sha256': tree_hash, 'evidence': str(evidence), 'public_changes': False}


def bounded_evidence(app_root: Path, evidence: Path) -> Path:
    root = (app_root.expanduser().resolve() / 'evidence').resolve()
    evidence = evidence.expanduser().resolve()
    try:
        evidence.relative_to(root)
    except ValueError as exc:
        raise OmekaDeployError('evidence path escapes Omeka evidence root') from exc
    if not evidence.is_dir():
        raise OmekaDeployError('evidence directory missing')
    return evidence


def rollback(app_root: Path, evidence: Path) -> dict[str, Any]:
    app_root = app_root.expanduser().resolve()
    evidence = bounded_evidence(app_root, evidence)
    try:
        state = json.loads((evidence / 'deployment-state.json').read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise OmekaDeployError('invalid deployment evidence') from exc
    if state.get('schema') != STATE_SCHEMA:
        raise OmekaDeployError('unsupported deployment evidence')
    current = app_root / 'current'
    if not current.is_symlink() or str(current.resolve()) != str(Path(state['current_target']).resolve()):
        raise OmekaDeployError('current release no longer matches recorded deployment')
    prior = state.get('prior_current_target')
    if prior:
        temp = app_root / f'.current.rollback-{os.getpid()}'
        try:
            temp.symlink_to(prior)
            os.replace(temp, current)
        finally:
            if temp.exists() or temp.is_symlink():
                temp.unlink()
    else:
        current.unlink()
    result = {
        'schema': STATE_SCHEMA,
        'rolled_back_at': utc_now(),
        'release_preserved': True,
        'database_unchanged': True,
        'persistent_files_preserved': True,
        'public_changes': False,
    }
    atomic_json(evidence / 'rollback-result.json', result)
    return {'status': 'rolled-back-pointer', **result}


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description='Business159 private Omeka S 4.2 deployment transaction')
    p.add_argument('--app-root', type=Path, default=APP_ROOT_DEFAULT)
    p.add_argument('--payload', type=Path)
    p.add_argument('--expected-tree-sha256')
    p.add_argument('--database-ini', type=Path)
    mode = p.add_mutually_exclusive_group()
    mode.add_argument('--apply', action='store_true')
    mode.add_argument('--rollback', type=Path)
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.rollback is not None:
            result = rollback(args.app_root, args.rollback)
        elif args.apply:
            if args.payload is None or args.expected_tree_sha256 is None or args.database_ini is None:
                raise OmekaDeployError('--apply requires payload, expected tree SHA-256, and database.ini file')
            result = apply(args.app_root, args.payload, args.expected_tree_sha256, args.database_ini)
        else:
            result = preflight(args.app_root, args.payload, args.expected_tree_sha256, args.database_ini)
    except (OmekaDeployError, OSError, json.JSONDecodeError) as exc:
        print(f'business159-omeka-deploy: {exc}', file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
