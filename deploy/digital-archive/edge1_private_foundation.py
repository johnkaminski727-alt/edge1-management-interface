#!/usr/bin/env python3
"""Bounded private Paperless/ArchiveBox deployment transaction for Edge1.

Default mode is read-only preflight. Apply is root-only and starts only the
reviewed loopback-bound Compose projects after verifying runtime, ports,
secret files, source policy and storage. This script never installs Docker,
changes DNS/certificates/firewall/Apache/authentication, or publishes a route.
Rollback stops only projects first started by the recorded transaction and
never deletes volumes or archive data.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import stat
import subprocess
import sys
import time
from typing import Any
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError

EXPECTED_REPO = Path('/opt/edge1-management-interface')
RUNTIME_ROOT = Path('/var/lib/wwcx-digital-archive')
EVIDENCE_ROOT = RUNTIME_ROOT / 'evidence/private-foundation'
CURRENT_STATE = RUNTIME_ROOT / 'private-foundation-current.json'
PAPERLESS_COMPOSE = Path('deploy/digital-archive/paperless/compose.yaml')
ARCHIVEBOX_COMPOSE = Path('deploy/digital-archive/archivebox/compose.yaml')
PAPERLESS_PROJECT = 'wwcx-paperless'
ARCHIVEBOX_PROJECT = 'wwcx-archivebox'
PAPERLESS_PORT = 8113
ARCHIVEBOX_PORT = 8114
STATE_SCHEMA = 'wwcx.digital-archive.private-foundation.v1'
REQUIRED_SECRET_MODE_MASK = 0o077
MIN_FREE_BYTES = 5 * 1024 * 1024 * 1024


class FoundationError(RuntimeError):
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
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=safe_env,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise FoundationError(f'command unavailable: {Path(command[0]).name}: {type(exc).__name__}') from exc


def require_success(command: list[str], *, env: dict[str, str] | None = None, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    result = run(command, env=env, timeout=timeout)
    if result.returncode != 0:
        raise FoundationError(f'command failed: {Path(command[0]).name} exit={result.returncode}')
    return result


def source_files(repo: Path) -> tuple[Path, Path]:
    return repo / PAPERLESS_COMPOSE, repo / ARCHIVEBOX_COMPOSE


def validate_compose_sources(repo: Path) -> dict[str, str]:
    paperless, archivebox = source_files(repo)
    for path in (paperless, archivebox):
        if path.is_symlink() or not path.is_file():
            raise FoundationError(f'missing or symlinked compose source: {path}')
    paperless_text = paperless.read_text(encoding='utf-8')
    archivebox_text = archivebox.read_text(encoding='utf-8')
    required_paperless = (
        'ghcr.io/paperless-ngx/paperless-ngx:3.0.5',
        '127.0.0.1:8113:8000',
        'PAPERLESS_DBPASS_FILE',
        'PAPERLESS_SECRET_KEY_FILE',
    )
    required_archivebox = (
        'archivebox/archivebox:0.7.4',
        '127.0.0.1:8114:8000',
        'PUBLIC_INDEX: "False"',
        'PUBLIC_SNAPSHOTS: "False"',
        'PUBLIC_ADD_VIEW: "False"',
        'SAVE_ARCHIVE_DOT_ORG: "False"',
    )
    missing = [item for item in required_paperless if item not in paperless_text]
    missing.extend(item for item in required_archivebox if item not in archivebox_text)
    if missing:
        raise FoundationError('compose source policy mismatch: ' + ', '.join(missing))
    forbidden = ('0.0.0.0:8113', '0.0.0.0:8114', ':latest')
    combined = paperless_text + '\n' + archivebox_text
    if any(item in combined for item in forbidden):
        raise FoundationError('compose source contains forbidden public/unpinned configuration')
    return {
        'paperless_sha256': sha256_file(paperless),
        'archivebox_sha256': sha256_file(archivebox),
    }


def docker_ready() -> tuple[bool, str]:
    docker = shutil.which('docker')
    if not docker:
        return False, 'docker-not-installed-or-not-on-path'
    result = run([docker, 'compose', 'version'], timeout=20)
    if result.returncode != 0:
        return False, 'docker-compose-plugin-unavailable'
    return True, 'ready'


def secret_status(path: Path | None) -> dict[str, Any]:
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
    if mode & REQUIRED_SECRET_MODE_MASK:
        return {'ready': False, 'reason': 'permissions-too-broad', 'mode': oct(mode)}
    if info.st_size < 32:
        return {'ready': False, 'reason': 'secret-too-short'}
    try:
        with path.open('rb') as handle:
            handle.read(1)
    except OSError:
        return {'ready': False, 'reason': 'unreadable'}
    return {'ready': True, 'reason': 'ready', 'mode': oct(mode), 'bytes': info.st_size}


def tcp_listener_present(port: int) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.25)
    try:
        return sock.connect_ex(('127.0.0.1', port)) == 0
    finally:
        sock.close()


def disk_status() -> dict[str, Any]:
    probe = RUNTIME_ROOT
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    usage = shutil.disk_usage(probe)
    return {
        'probe': str(probe),
        'free_bytes': usage.free,
        'total_bytes': usage.total,
        'minimum_free_bytes': MIN_FREE_BYTES,
        'ready': usage.free >= MIN_FREE_BYTES,
    }


def compose_env(db_password_file: Path, secret_key_file: Path) -> dict[str, str]:
    return {
        'PAPERLESS_DB_PASSWORD_FILE': str(db_password_file.expanduser().resolve()),
        'PAPERLESS_SECRET_KEY_FILE': str(secret_key_file.expanduser().resolve()),
    }


def compose_command(repo: Path, project: str, relative_file: Path, *args: str) -> list[str]:
    docker = shutil.which('docker') or '/usr/bin/docker'
    return [
        docker, 'compose',
        '--project-name', project,
        '--file', str(repo / relative_file),
        *args,
    ]


def project_running(repo: Path, project: str, relative_file: Path, env: dict[str, str]) -> bool:
    result = run(compose_command(repo, project, relative_file, 'ps', '--status', 'running', '--services'), env=env, timeout=30)
    return result.returncode == 0 and bool(result.stdout.strip())


def validate_compose_config(repo: Path, env: dict[str, str]) -> None:
    require_success(compose_command(repo, PAPERLESS_PROJECT, PAPERLESS_COMPOSE, 'config', '--quiet'), env=env, timeout=30)
    require_success(compose_command(repo, ARCHIVEBOX_PROJECT, ARCHIVEBOX_COMPOSE, 'config', '--quiet'), env=env, timeout=30)


def preflight(
    repo: Path = EXPECTED_REPO,
    db_password_file: Path | None = None,
    secret_key_file: Path | None = None,
) -> dict[str, Any]:
    repo = repo.expanduser().resolve()
    if not repo.is_dir():
        raise FoundationError(f'repository missing: {repo}')
    source_hashes = validate_compose_sources(repo)
    runtime_ok, runtime_reason = docker_ready()
    db_status = secret_status(db_password_file)
    key_status = secret_status(secret_key_file)
    storage = disk_status()
    port_state = {
        str(PAPERLESS_PORT): tcp_listener_present(PAPERLESS_PORT),
        str(ARCHIVEBOX_PORT): tcp_listener_present(ARCHIVEBOX_PORT),
    }
    blockers: list[str] = []
    if not runtime_ok:
        blockers.append(runtime_reason)
    if not db_status['ready']:
        blockers.append('paperless-db-secret-' + db_status['reason'])
    if not key_status['ready']:
        blockers.append('paperless-key-secret-' + key_status['reason'])
    if not storage['ready']:
        blockers.append('insufficient-free-storage')
    return {
        'status': 'preflight-ok' if not blockers else 'preflight-blocked',
        'repo': str(repo),
        'container_runtime_ready': runtime_ok,
        'container_runtime_reason': runtime_reason,
        'secret_files': {'db_password': db_status, 'secret_key': key_status},
        'loopback_listener_present': port_state,
        'source_hashes': source_hashes,
        'storage_root': str(RUNTIME_ROOT),
        'storage': storage,
        'public_changes': False,
        'installs_container_runtime': False,
        'deletes_volumes': False,
        'canonical_data_ingestion': False,
        'blockers': blockers,
    }


def ensure_runtime_dirs() -> None:
    paths = (
        RUNTIME_ROOT,
        RUNTIME_ROOT / 'paperless/postgres',
        RUNTIME_ROOT / 'paperless/valkey',
        RUNTIME_ROOT / 'paperless/data',
        RUNTIME_ROOT / 'paperless/media',
        RUNTIME_ROOT / 'paperless/export',
        RUNTIME_ROOT / 'paperless/consume',
        RUNTIME_ROOT / 'archivebox/data',
        EVIDENCE_ROOT,
    )
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)
        os.chmod(path, 0o750)


def wait_http(url: str, timeout_seconds: int = 120) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_error = 'not-attempted'
    while time.monotonic() < deadline:
        try:
            req = urllib_request.Request(url, method='GET', headers={'User-Agent': 'wwcx-digital-archive-preflight/1'})
            with urllib_request.urlopen(req, timeout=3) as response:
                return {'ready': True, 'status': int(response.status)}
        except HTTPError as exc:
            if 200 <= exc.code < 500:
                return {'ready': True, 'status': int(exc.code)}
            last_error = f'http-{exc.code}'
        except (URLError, TimeoutError, OSError) as exc:
            last_error = type(exc).__name__
        time.sleep(2)
    return {'ready': False, 'reason': last_error}


def atomic_json(path: Path, value: dict[str, Any], mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f'.{path.name}.tmp-{os.getpid()}')
    temp.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    os.chmod(temp, mode)
    os.replace(temp, path)


def rollback_started_projects(
    repo: Path,
    state: dict[str, Any],
    env: dict[str, str],
    evidence: Path,
) -> dict[str, Any]:
    stopped: list[str] = []
    failures: list[str] = []
    for project, relative in (
        (ARCHIVEBOX_PROJECT, ARCHIVEBOX_COMPOSE),
        (PAPERLESS_PROJECT, PAPERLESS_COMPOSE),
    ):
        project_state = state.get('projects', {}).get(project, {})
        if project_state.get('started_by_transaction') is not True or project_state.get('was_running') is not False:
            continue
        result = run(compose_command(repo, project, relative, 'down'), env=env, timeout=180)
        if result.returncode == 0:
            stopped.append(project)
        else:
            failures.append(project)
    rollback_result = {
        'schema': STATE_SCHEMA,
        'rolled_back_at': utc_now(),
        'stopped_projects': stopped,
        'failed_projects': failures,
        'volumes_preserved': True,
        'runtime_data_preserved': True,
        'public_changes': False,
    }
    atomic_json(evidence / 'rollback-result.json', rollback_result)
    return rollback_result


def apply(repo: Path, db_password_file: Path, secret_key_file: Path) -> dict[str, Any]:
    if os.geteuid() != 0:
        raise FoundationError('--apply requires root')
    repo = repo.expanduser().resolve()
    if repo != EXPECTED_REPO:
        raise FoundationError('live apply is restricted to the canonical Edge1 management repository')
    info = preflight(repo, db_password_file, secret_key_file)
    if info['blockers']:
        raise FoundationError('preflight blocked: ' + ', '.join(info['blockers']))
    env = compose_env(db_password_file, secret_key_file)
    validate_compose_config(repo, env)
    paperless_was_running = project_running(repo, PAPERLESS_PROJECT, PAPERLESS_COMPOSE, env)
    archivebox_was_running = project_running(repo, ARCHIVEBOX_PROJECT, ARCHIVEBOX_COMPOSE, env)
    if not paperless_was_running and info['loopback_listener_present'][str(PAPERLESS_PORT)]:
        raise FoundationError('port 8113 is already occupied by an unverified listener')
    if not archivebox_was_running and info['loopback_listener_present'][str(ARCHIVEBOX_PORT)]:
        raise FoundationError('port 8114 is already occupied by an unverified listener')

    ensure_runtime_dirs()
    stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    evidence = EVIDENCE_ROOT / f'{stamp}-{os.getpid()}'
    evidence.mkdir(parents=True, exist_ok=False)
    os.chmod(evidence, 0o700)
    state = {
        'schema': STATE_SCHEMA,
        'created_at': utc_now(),
        'repo': str(repo),
        'source_hashes': info['source_hashes'],
        'projects': {
            PAPERLESS_PROJECT: {'was_running': paperless_was_running, 'started_by_transaction': False},
            ARCHIVEBOX_PROJECT: {'was_running': archivebox_was_running, 'started_by_transaction': False},
        },
        'public_changes': False,
        'volume_deletion_authorized': False,
        'evidence': str(evidence),
    }
    atomic_json(evidence / 'deployment-state.json', state)

    try:
        if not paperless_was_running:
            require_success(compose_command(repo, PAPERLESS_PROJECT, PAPERLESS_COMPOSE, 'up', '-d'), env=env, timeout=300)
            state['projects'][PAPERLESS_PROJECT]['started_by_transaction'] = True
            atomic_json(evidence / 'deployment-state.json', state)
        if not archivebox_was_running:
            require_success(compose_command(repo, ARCHIVEBOX_PROJECT, ARCHIVEBOX_COMPOSE, 'up', '-d'), env=env, timeout=300)
            state['projects'][ARCHIVEBOX_PROJECT]['started_by_transaction'] = True
            atomic_json(evidence / 'deployment-state.json', state)

        paperless_health = wait_http(f'http://127.0.0.1:{PAPERLESS_PORT}/')
        archivebox_health = wait_http(f'http://127.0.0.1:{ARCHIVEBOX_PORT}/')
        if not paperless_health.get('ready') or not archivebox_health.get('ready'):
            raise FoundationError('private archive service health verification failed')
        state['verified_at'] = utc_now()
        state['health'] = {'paperless': paperless_health, 'archivebox': archivebox_health}
        atomic_json(evidence / 'deployment-state.json', state)
        atomic_json(CURRENT_STATE, {'schema': STATE_SCHEMA, 'evidence': str(evidence), 'verified_at': state['verified_at']})
        return {
            'status': 'private-foundation-active',
            'paperless': paperless_health,
            'archivebox': archivebox_health,
            'evidence': str(evidence),
            'public_changes': False,
            'canonical_data_ingestion': False,
        }
    except FoundationError as exc:
        rollback_result = rollback_started_projects(repo, state, env, evidence)
        atomic_json(evidence / 'failure.json', {
            'schema': STATE_SCHEMA,
            'failed_at': utc_now(),
            'failure_type': type(exc).__name__,
            'automatic_rollback': rollback_result,
        })
        status = 'complete' if not rollback_result['failed_projects'] else 'partial'
        raise FoundationError(f'private foundation activation failed; automatic rollback={status}; evidence={evidence}') from exc


def bounded_evidence_path(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    root = EVIDENCE_ROOT.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise FoundationError('rollback evidence path escapes managed evidence root') from exc
    if not resolved.name or not resolved.is_dir():
        raise FoundationError('rollback evidence directory is missing')
    return resolved


def rollback(repo: Path, evidence: Path, db_password_file: Path, secret_key_file: Path) -> dict[str, Any]:
    if os.geteuid() != 0:
        raise FoundationError('--rollback requires root')
    repo = repo.expanduser().resolve()
    if repo != EXPECTED_REPO:
        raise FoundationError('live rollback is restricted to the canonical Edge1 management repository')
    evidence = bounded_evidence_path(evidence)
    state_path = evidence / 'deployment-state.json'
    state = json.loads(state_path.read_text(encoding='utf-8'))
    if state.get('schema') != STATE_SCHEMA or state.get('repo') != str(repo):
        raise FoundationError('unsupported or mismatched deployment state')
    if state.get('source_hashes') != validate_compose_sources(repo):
        raise FoundationError('compose sources changed since deployment; refusing blind rollback')
    env = compose_env(db_password_file, secret_key_file)
    result = rollback_started_projects(repo, state, env, evidence)
    if result['failed_projects']:
        raise FoundationError('rollback could not stop all transaction-started projects')
    return {'status': 'rolled-back-private-foundation', **result}


def rollback_last(repo: Path, db_password_file: Path, secret_key_file: Path) -> dict[str, Any]:
    try:
        pointer = json.loads(CURRENT_STATE.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise FoundationError('current deployment pointer is unavailable') from exc
    if pointer.get('schema') != STATE_SCHEMA or not isinstance(pointer.get('evidence'), str):
        raise FoundationError('current deployment pointer is invalid')
    return rollback(repo, Path(pointer['evidence']), db_password_file, secret_key_file)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description='WW.CX private Digital Archive Edge1 foundation')
    p.add_argument('--repo', type=Path, default=EXPECTED_REPO)
    p.add_argument('--paperless-db-password-file', type=Path)
    p.add_argument('--paperless-secret-key-file', type=Path)
    mode = p.add_mutually_exclusive_group()
    mode.add_argument('--apply', action='store_true')
    mode.add_argument('--rollback', type=Path)
    mode.add_argument('--rollback-last', action='store_true')
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.apply or args.rollback is not None or args.rollback_last:
            if args.paperless_db_password_file is None or args.paperless_secret_key_file is None:
                raise FoundationError('mutation requires both Paperless runtime secret-file paths')
        if args.rollback is not None:
            value = rollback(args.repo, args.rollback, args.paperless_db_password_file, args.paperless_secret_key_file)
        elif args.rollback_last:
            value = rollback_last(args.repo, args.paperless_db_password_file, args.paperless_secret_key_file)
        elif args.apply:
            value = apply(args.repo, args.paperless_db_password_file, args.paperless_secret_key_file)
        else:
            value = preflight(args.repo, args.paperless_db_password_file, args.paperless_secret_key_file)
    except (FoundationError, OSError, json.JSONDecodeError) as exc:
        print(f'digital-archive-private-foundation: {exc}', file=sys.stderr)
        return 2
    print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
