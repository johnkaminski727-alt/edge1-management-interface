#!/usr/bin/env python3
"""Backup-first live Alpha activation for Cookie Monster on Edge1.

Default mode is read-only preflight. ``--apply`` is a root-only, bounded
non-production activation that:

* populates only the fixed ``alpha-staging`` synthetic dataset when empty;
* enables only that existing registry entry (non-production + read-only stay true);
* dispatches the fixed path-free Alpha job contract;
* exercises one fixed Fengus systemd work item through its hardened unit;
* writes a live acceptance snapshot; and
* stages the Cookie Monster operator view with bounded staging detail outside the public web root.

No DNS, certificate, firewall, Apache, authentication, canonical archive, public
web root or external account is changed. Rollback restores control and staged
operator-view state while intentionally preserving generated/source/Fengus evidence.
"""
from __future__ import annotations

import argparse
import datetime as dt
import grp
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
from typing import Any

EXPECTED_REPO = Path('/opt/edge1-management-interface')
REGISTRY_PATH = Path('/etc/wwcx-cookie-monster/datasets.json')
DATASET_ROOT = Path('/srv/cookie-monster/datasets')
DATASET_SLUG = 'alpha-staging'
DATASET_PATH = DATASET_ROOT / DATASET_SLUG
GENERATED_ROOT = Path('/var/lib/cookie-monster-alpha/generated')
GENERATED_PATH = GENERATED_ROOT / DATASET_SLUG
JOB_PATH = Path('/var/lib/cookie-monster-alpha/jobs/alpha-staging.json')
FENGUS_INBOX = Path('/var/lib/cookie-monster-alpha/fengus/inbox')
FENGUS_OUTBOX = Path('/var/lib/cookie-monster-alpha/fengus/outbox')
FENGUS_GROUP = 'cookie-monster-fengus'
FENGUS_UNIT = Path('/etc/systemd/system/cookie-monster-fengus-worker@.service')
COCKPIT_STAGE_ROOT = Path('/var/lib/cookie-monster-alpha/operator-view')
BACKUP_ROOT = Path('/var/backups')
CURRENT_STATE = Path('/var/lib/cookie-monster-alpha/activation-current.json')
STATE_SCHEMA = 'wwcx.cookie-monster.edge1-activation.v1'
ACCEPTANCE_SCHEMA = 'wwcx.cookie-monster.acceptance.v1'
REGISTRY_SCHEMA = 'wwcx.cookie-monster.datasets.v1'
STATUS_SCHEMA = 'wwcx.cookie-monster.alpha.v1'
WORK_SCHEMA = 'wwcx.cookie-monster.fengus-work.v1'
RESULT_SCHEMA = 'wwcx.cookie-monster.fengus-result.v1'
ACTOR = 'edge1-cookie-monster-activation'
ALLOWED_DATASET_FIELDS = {'enabled', 'non_production', 'read_only', 'description'}

_PHRASE = b'Cookie Monster eats ASCII for brunch.\n'
SYNTHETIC_FILES: dict[str, bytes] = {
    'ascii-brunch.txt': _PHRASE,
    'ascii-brunch-copy.txt': _PHRASE,
    'facts.json': b'{"mascot":"cookie-monster","mode":"alpha","source":"edge1-synthetic-staging"}\n',
    'blob.bin': bytes(range(64)),
}


class ActivationError(RuntimeError):
    pass


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_bytes(path: Path, value: bytes, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f'.{path.name}.tmp-{os.getpid()}')
    with temp.open('wb') as handle:
        handle.write(value)
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(temp, mode)
    os.replace(temp, path)


def atomic_json(path: Path, value: dict[str, Any], mode: int = 0o600) -> None:
    atomic_bytes(path, (json.dumps(value, indent=2, sort_keys=True) + '\n').encode('utf-8'), mode)


def read_json(path: Path) -> dict[str, Any]:
    if path.is_symlink():
        raise ActivationError(f'symlink JSON path rejected: {path}')
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise ActivationError(f'invalid JSON object {path}: {type(exc).__name__}') from exc
    if not isinstance(value, dict):
        raise ActivationError(f'JSON value must be an object: {path}')
    return value


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    value = read_json(path)
    if set(value) != {'schema', 'datasets'} or value.get('schema') != REGISTRY_SCHEMA:
        raise ActivationError('unsupported dataset registry')
    datasets = value.get('datasets')
    if not isinstance(datasets, dict):
        raise ActivationError('dataset registry datasets must be an object')
    entry = datasets.get(DATASET_SLUG)
    if not isinstance(entry, dict):
        raise ActivationError('dataset registry missing alpha-staging')
    extra = sorted(set(entry) - ALLOWED_DATASET_FIELDS)
    if extra:
        raise ActivationError('alpha-staging contains unexpected fields: ' + ', '.join(extra))
    if type(entry.get('enabled')) is not bool:
        raise ActivationError('alpha-staging enabled must be boolean')
    if entry.get('non_production') is not True or entry.get('read_only') is not True:
        raise ActivationError('alpha-staging must remain non-production and read-only')
    description = entry.get('description', '')
    if not isinstance(description, str) or len(description) > 500:
        raise ActivationError('alpha-staging description is invalid')
    return value


def expected_source_state() -> dict[str, dict[str, Any]]:
    return {
        name: {'sha256': sha256_bytes(value), 'size': len(value)}
        for name, value in sorted(SYNTHETIC_FILES.items())
    }


def dataset_state(path: Path = DATASET_PATH) -> tuple[str, dict[str, dict[str, Any]]]:
    if path.is_symlink():
        raise ActivationError('alpha-staging dataset may not be a symlink')
    if not path.exists():
        return 'missing', {}
    if not path.is_dir():
        raise ActivationError('alpha-staging path is not a directory')
    children = sorted(path.iterdir(), key=lambda item: item.name)
    if not children:
        return 'empty', {}
    actual: dict[str, dict[str, Any]] = {}
    for item in children:
        if item.is_symlink() or not item.is_file():
            return 'conflict', {}
        actual[item.name] = {'sha256': sha256_file(item), 'size': item.stat().st_size}
    return ('synthetic-ready' if actual == expected_source_state() else 'conflict'), actual


def _required_repo_files(repo: Path) -> tuple[Path, ...]:
    return (
        repo / 'server/cookie_monster_contract.py',
        repo / 'server/cookie_monster_dispatch.py',
        repo / 'server/cookie_monster_fengus_worker.py',
        repo / 'deploy/cookie_monster_runtime_publish.py',
    )


def verify_fengus_foundation(
    unit_path: Path = FENGUS_UNIT,
    inbox: Path = FENGUS_INBOX,
    outbox: Path = FENGUS_OUTBOX,
    group_name: str = FENGUS_GROUP,
) -> dict[str, Any]:
    if unit_path.is_symlink() or not unit_path.is_file():
        raise ActivationError('Fengus hardened worker unit is not installed')
    try:
        group = grp.getgrnam(group_name)
    except KeyError as exc:
        raise ActivationError('Fengus service group is missing') from exc
    for label, path in (('inbox', inbox), ('outbox', outbox)):
        if path.is_symlink() or not path.is_dir():
            raise ActivationError(f'Fengus {label} directory is missing or invalid')
    return {'unit': str(unit_path), 'group_gid': group.gr_gid, 'inbox': str(inbox), 'outbox': str(outbox)}


def preflight(
    repo: Path = EXPECTED_REPO,
    registry_path: Path = REGISTRY_PATH,
    dataset_path: Path = DATASET_PATH,
    generated_path: Path = GENERATED_PATH,
    current_state: Path = CURRENT_STATE,
    verify_runtime: bool = True,
) -> dict[str, Any]:
    repo = repo.expanduser().resolve()
    if not repo.is_dir():
        raise ActivationError(f'repository missing: {repo}')
    missing = [str(path) for path in _required_repo_files(repo) if not path.is_file() or path.is_symlink()]
    if missing:
        raise ActivationError('required activation sources missing or symlinked: ' + ', '.join(missing))
    registry = load_registry(registry_path)
    state, source = dataset_state(dataset_path)
    if state == 'missing':
        raise ActivationError('Cookie Monster foundation is not installed: alpha-staging directory is missing')
    if state == 'conflict':
        raise ActivationError('alpha-staging contains data outside the deterministic synthetic activation set')
    if dataset_path.parent.is_symlink():
        raise ActivationError('alpha-staging dataset root may not be a symlink')
    dataset_mode = stat.S_IMODE(dataset_path.stat().st_mode)
    if dataset_mode & 0o222:
        raise ActivationError('alpha-staging directory must remain filesystem read-only')
    if state == 'synthetic-ready':
        for child in dataset_path.iterdir():
            if stat.S_IMODE(child.stat().st_mode) & 0o222:
                raise ActivationError('synthetic alpha-staging files must remain filesystem read-only')
    entry = registry['datasets'][DATASET_SLUG]
    if entry['enabled'] and state != 'synthetic-ready':
        raise ActivationError('enabled alpha-staging must contain the verified synthetic activation set')
    generated = generated_path.exists()
    if generated and (generated_path.is_symlink() or not generated_path.is_dir()):
        raise ActivationError('generated alpha-staging path is not a regular directory')
    fengus_foundation = verify_fengus_foundation() if verify_runtime else None
    return {
        'status': 'preflight-ok',
        'repo': str(repo),
        'dataset': DATASET_SLUG,
        'dataset_state': state,
        'dataset_enabled': entry['enabled'],
        'non_production': entry['non_production'],
        'read_only': entry['read_only'],
        'synthetic_files': len(source),
        'generated_present': generated,
        'current_activation_present': current_state.is_file() and not current_state.is_symlink(),
        'fengus_foundation': fengus_foundation,
        'cockpit_stage': str(COCKPIT_STAGE_ROOT),
        'public_changes': False,
        'canonical_archive_access': False,
    }


def prepare_synthetic_dataset(path: Path = DATASET_PATH) -> dict[str, dict[str, Any]]:
    state, _ = dataset_state(path)
    if state == 'synthetic-ready':
        return expected_source_state()
    if state != 'empty':
        raise ActivationError(f'alpha-staging must be empty before synthetic preparation (state={state})')
    for name, value in SYNTHETIC_FILES.items():
        atomic_bytes(path / name, value, 0o444)
    os.chmod(path, 0o555)
    state, actual = dataset_state(path)
    if state != 'synthetic-ready':
        raise ActivationError('synthetic alpha-staging verification failed after write')
    return actual


def enable_dataset(registry_path: Path = REGISTRY_PATH) -> dict[str, Any]:
    registry = load_registry(registry_path)
    entry = registry['datasets'][DATASET_SLUG]
    if entry['enabled'] is not True:
        entry['enabled'] = True
        atomic_json(registry_path, registry, mode=0o640)
    verified = load_registry(registry_path)
    if verified['datasets'][DATASET_SLUG]['enabled'] is not True:
        raise ActivationError('failed to enable alpha-staging')
    return verified


def run(command: list[str], *, cwd: Path | None = None, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    env = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8'}
    try:
        result = subprocess.run(
            command,
            cwd=str(cwd) if cwd is not None else None,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ActivationError(f'command failed to execute: {Path(command[0]).name}: {type(exc).__name__}') from exc
    if result.returncode != 0:
        raise ActivationError(f'command failed: {Path(command[0]).name} exit={result.returncode}')
    return result


def run_json(command: list[str], *, cwd: Path | None = None, timeout: int = 120) -> dict[str, Any]:
    result = run(command, cwd=cwd, timeout=timeout)
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ActivationError(f'command returned invalid JSON: {Path(command[0]).name}') from exc
    if not isinstance(value, dict):
        raise ActivationError('command JSON result must be an object')
    return value


def create_job(repo: Path) -> dict[str, Any]:
    return run_json([
        '/usr/bin/python3', str(repo / 'server/cookie_monster_contract.py'), 'make',
        '--dataset', DATASET_SLUG,
        '--requested-by', ACTOR,
        '--max-files', '50',
    ], cwd=repo)


def write_job(path: Path, job: dict[str, Any]) -> None:
    created_parent = not path.parent.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    if created_parent:
        os.chmod(path.parent, 0o750)
    atomic_json(path, job, mode=0o640)


def dispatch_job(repo: Path, job_path: Path, registry_path: Path, dataset_root: Path, generated_root: Path) -> dict[str, Any]:
    return run_json([
        '/usr/bin/python3', str(repo / 'server/cookie_monster_dispatch.py'),
        '--job', str(job_path),
        '--registry', str(registry_path),
        '--dataset-root', str(dataset_root),
        '--output-root', str(generated_root),
    ], cwd=repo, timeout=300)


def read_jsonl_first(path: Path) -> dict[str, Any]:
    try:
        with path.open('r', encoding='utf-8') as handle:
            for line in handle:
                if line.strip():
                    value = json.loads(line)
                    if isinstance(value, dict):
                        return value
                    break
    except (OSError, json.JSONDecodeError) as exc:
        raise ActivationError(f'cannot read generated record: {type(exc).__name__}') from exc
    raise ActivationError('generated knowledge records are empty')


def _work_request(job: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    asset = record.get('source_asset_id')
    digest = asset[7:] if isinstance(asset, str) and asset.startswith('sha256:') else ''
    if len(digest) != 64 or any(char not in '0123456789abcdef' for char in digest):
        raise ActivationError('generated record missing bounded source asset id')
    work_id = 'work-' + hashlib.sha256(asset.encode('utf-8')).hexdigest()[:24]
    return {
        'schema': WORK_SCHEMA,
        'job_id': job['job_id'],
        'work_id': work_id,
        'operation': 'text.token-stats',
        'source_asset_id': asset,
        'payload': {'text': _PHRASE.decode('utf-8')},
    }


def run_fengus(
    job: dict[str, Any],
    generated_path: Path = GENERATED_PATH,
    inbox: Path = FENGUS_INBOX,
    outbox: Path = FENGUS_OUTBOX,
    group_name: str = FENGUS_GROUP,
) -> dict[str, Any]:
    record = read_jsonl_first(generated_path / 'knowledge-records.jsonl')
    request = _work_request(job, record)
    work_id = request['work_id']
    request_path = inbox / f'{work_id}.json'
    result_path = outbox / f'{work_id}.json'
    try:
        gid = grp.getgrnam(group_name).gr_gid
    except KeyError as exc:
        raise ActivationError('Fengus service group is missing') from exc
    inbox.mkdir(parents=True, exist_ok=True)
    if request_path.exists():
        if request_path.is_symlink() or read_json(request_path) != request:
            raise ActivationError('existing Fengus request conflicts with deterministic work item')
    else:
        atomic_json(request_path, request, mode=0o640)
    os.chown(request_path, 0, gid)
    unit = f'cookie-monster-fengus-worker@{work_id}.service'
    run(['/bin/systemctl', 'start', unit], timeout=60)
    result = read_json(result_path)
    result_hash = result.get('result_hash')
    digest = result_hash[7:] if isinstance(result_hash, str) and result_hash.startswith('sha256:') else ''
    if (
        result.get('schema') != RESULT_SCHEMA
        or result.get('work_id') != work_id
        or result.get('operation') != request['operation']
        or len(digest) != 64
        or any(char not in '0123456789abcdef' for char in digest)
    ):
        raise ActivationError('Fengus result failed bounded schema verification')
    return {'unit': unit, 'work_id': work_id, 'result_hash': result_hash}


def update_fengus_status(generated_path: Path, fengus: dict[str, Any]) -> dict[str, Any]:
    status_path = generated_path / 'status.json'
    status = read_json(status_path)
    if status.get('schema') != STATUS_SCHEMA:
        raise ActivationError('generated status schema is not Cookie Monster Alpha v1')
    status['fengus'] = {
        'connected': True,
        'mode': 'bounded-systemd-worker-verified',
        'jobs_active': 0,
        'jobs_completed': 1,
        'jobs_failed': 0,
    }
    atomic_json(status_path, status, mode=0o600)
    audit_path = generated_path / 'activation-audit.jsonl'
    event = {
        'schema': STATE_SCHEMA,
        'timestamp': utc_now(),
        'event': 'fengus.bounded-work.verified',
        'work_id': fengus['work_id'],
        'result_hash': fengus.get('result_hash'),
    }
    with audit_path.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(event, sort_keys=True, separators=(',', ':')) + '\n')
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(audit_path, 0o600)
    return status


def verify_provenance(status: dict[str, Any], dataset_path: Path) -> list[str]:
    gaps: list[str] = []
    records = status.get('knowledge_records')
    if not isinstance(records, list):
        return ['knowledge_records missing']
    for record in records:
        if not isinstance(record, dict):
            gaps.append('non-object knowledge record')
            continue
        location = record.get('source_asset_location')
        source_asset_id = record.get('source_asset_id')
        if not isinstance(location, str) or '/' in location or '\\' in location:
            gaps.append('invalid source asset location')
            continue
        source = dataset_path / location
        if not source.is_file() or source.is_symlink():
            gaps.append(f'missing source: {location}')
            continue
        if source_asset_id != f'sha256:{sha256_file(source)}':
            gaps.append(f'hash mismatch: {location}')
    return gaps


def write_live_acceptance(
    generated_path: Path,
    dataset_path: Path,
    source_before: dict[str, dict[str, Any]],
    source_after: dict[str, dict[str, Any]],
    fengus: dict[str, Any],
) -> dict[str, Any]:
    status = read_json(generated_path / 'status.json')
    if status.get('schema') != STATUS_SCHEMA:
        raise ActivationError('generated status has unexpected schema')
    summary = status.get('summary') if isinstance(status.get('summary'), dict) else {}
    gaps = verify_provenance(status, dataset_path)
    duplicate_groups = summary.get('duplicate_groups')
    unauthorized_writes = summary.get('unauthorized_source_writes')
    if type(duplicate_groups) is not int or duplicate_groups < 0:
        raise ActivationError('generated duplicate group count is invalid')
    if type(unauthorized_writes) is not int or unauthorized_writes < 0:
        raise ActivationError('generated unauthorized-write count is invalid')
    criteria = {
        'synthetic_source_immutable': {'pass': source_before == source_after, 'value': len(source_after), 'detail': ''},
        'duplicate_detection': {'pass': duplicate_groups >= 1, 'value': duplicate_groups, 'detail': ''},
        'zero_unauthorized_source_writes': {'pass': unauthorized_writes == 0, 'value': unauthorized_writes, 'detail': ''},
        'zero_provenance_gaps': {'pass': not gaps, 'value': len(gaps), 'detail': ''},
        'fengus_bounded_systemd_work': {'pass': bool(fengus.get('result_hash')), 'value': fengus.get('work_id'), 'detail': ''},
    }
    passed = all(row['pass'] for row in criteria.values())
    report = {
        'schema': ACCEPTANCE_SCHEMA,
        'generated_at': utc_now(),
        'dataset': DATASET_SLUG,
        'mode': 'synthetic-non-production-live',
        'result': 'pass' if passed else 'fail',
        'summary': {
            'assets': summary.get('knowledge_records', 0),
            'unique_assets': summary.get('unique_assets', 0),
            'duplicate_groups': duplicate_groups,
            'provenance_gaps': len(gaps),
            'unauthorized_source_writes': unauthorized_writes,
            'fengus_jobs_outside_allowlist': 0,
        },
        'criteria': criteria,
    }
    atomic_json(generated_path / 'acceptance.json', report, mode=0o600)
    if not passed:
        failed = ', '.join(name for name, row in criteria.items() if not row['pass'])
        raise ActivationError('live alpha acceptance failed: ' + failed)
    return report


def _runtime_backup_dirs(backup_root: Path = BACKUP_ROOT) -> set[Path]:
    if not backup_root.is_dir():
        return set()
    return {
        path.resolve() for path in backup_root.iterdir()
        if path.is_dir() and not path.is_symlink() and path.name.startswith('wwcx-cookie-monster-runtime-')
    }


def publish(repo: Path, generated_path: Path) -> dict[str, Any]:
    before = _runtime_backup_dirs(BACKUP_ROOT)
    command = [
        '/usr/bin/python3', str(repo / 'deploy/cookie_monster_runtime_publish.py'),
        '--repo-root', str(repo),
        '--generated-root', str(generated_path),
        '--web-root', str(COCKPIT_STAGE_ROOT),
        '--backup-root', str(BACKUP_ROOT),
        '--publish-detail',
        '--apply',
    ]
    try:
        result = run_json(command, cwd=repo, timeout=120)
    except ActivationError:
        created = _runtime_backup_dirs(BACKUP_ROOT) - before
        if len(created) == 1:
            recovery = next(iter(created))
            try:
                run([
                    '/usr/bin/python3', str(repo / 'deploy/cookie_monster_runtime_publish.py'),
                    '--web-root', str(COCKPIT_STAGE_ROOT),
                    '--rollback', str(recovery),
                ], cwd=repo, timeout=120)
            except ActivationError:
                pass
        raise
    backup = result.get('backup')
    if not isinstance(backup, str):
        raise ActivationError('publisher did not return a rollback backup')
    _safe_publisher_backup_path(Path(backup))
    return result


def _backup_file(source: Path, destination: Path) -> dict[str, Any]:
    state = {'present': source.is_file() and not source.is_symlink()}
    if state['present']:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        state['sha256'] = sha256_file(destination)
    elif source.exists():
        raise ActivationError(f'managed state is not a regular file: {source}')
    return state


def create_backup(
    backup_root: Path,
    registry_path: Path,
    job_path: Path,
    dataset_status: str,
    repo: Path,
) -> tuple[Path, dict[str, Any]]:
    stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup = backup_root / f'wwcx-cookie-monster-alpha-activation-{stamp}-{os.getpid()}'
    backup.mkdir(parents=True, exist_ok=False)
    state: dict[str, Any] = {
        'schema': STATE_SCHEMA,
        'created_at': utc_now(),
        'dataset': DATASET_SLUG,
        'dataset_state_before': dataset_status,
        'files': {
            'registry': _backup_file(registry_path, backup / 'datasets.json'),
            'job': _backup_file(job_path, backup / 'alpha-staging-job.json'),
        },
        'publisher_backup': None,
        'publisher_script': _backup_file(repo / 'deploy/cookie_monster_runtime_publish.py', backup / 'runtime-publisher.py'),
        'generated_evidence_preserved': True,
        'source_evidence_preserved': True,
        'fengus_evidence_preserved': True,
    }
    atomic_json(backup / 'activation-state.json', state, mode=0o600)
    return backup, state


def _restore_file(backup: Path, state: dict[str, Any], key: str, backup_name: str, destination: Path) -> None:
    item = state['files'][key]
    if item.get('present') is True:
        source = backup / backup_name
        if not source.is_file() or source.is_symlink():
            raise ActivationError(f'activation backup payload missing: {source}')
        if item.get('sha256') and sha256_file(source) != item['sha256']:
            raise ActivationError(f'activation backup hash mismatch: {source}')
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    elif destination.is_file() or destination.is_symlink():
        destination.unlink()


def _safe_backup_path(value: Path, backup_root: Path = BACKUP_ROOT) -> Path:
    backup = value.expanduser().resolve()
    root = backup_root.expanduser().resolve()
    try:
        backup.relative_to(root)
    except ValueError as exc:
        raise ActivationError('activation backup must remain under configured backup root') from exc
    if not backup.name.startswith('wwcx-cookie-monster-alpha-activation-'):
        raise ActivationError('activation backup name is invalid')
    return backup


def _safe_publisher_backup_path(value: Path, backup_root: Path = BACKUP_ROOT) -> Path:
    backup = value.expanduser().resolve()
    root = backup_root.expanduser().resolve()
    try:
        backup.relative_to(root)
    except ValueError as exc:
        raise ActivationError('publisher backup must remain under configured backup root') from exc
    if not backup.name.startswith('wwcx-cookie-monster-runtime-'):
        raise ActivationError('publisher backup name is invalid')
    return backup


def _authorized_mutation_repo(repo: Path) -> Path:
    candidate = repo.expanduser().resolve()
    expected = EXPECTED_REPO.expanduser().resolve()
    if candidate != expected:
        raise ActivationError('mutating activation is restricted to the canonical Edge1 management repository')
    return candidate


def rollback(backup: Path, repo: Path = EXPECTED_REPO) -> dict[str, Any]:
    if os.geteuid() != 0:
        raise ActivationError('rollback requires root')
    repo = _authorized_mutation_repo(repo)
    backup = _safe_backup_path(backup)
    state = read_json(backup / 'activation-state.json')
    if state.get('schema') != STATE_SCHEMA or not isinstance(state.get('files'), dict):
        raise ActivationError('unsupported activation backup state')
    publisher_backup = state.get('publisher_backup')
    if publisher_backup:
        if not isinstance(publisher_backup, str):
            raise ActivationError('publisher backup state is invalid')
        safe_publisher_backup = _safe_publisher_backup_path(Path(publisher_backup))
        publisher_script = backup / 'runtime-publisher.py'
        publisher_state = state.get('publisher_script')
        if not isinstance(publisher_state, dict) or publisher_state.get('present') is not True:
            raise ActivationError('activation backup is missing the exact runtime publisher')
        expected_publisher_hash = publisher_state.get('sha256')
        if not isinstance(expected_publisher_hash, str) or sha256_file(publisher_script) != expected_publisher_hash:
            raise ActivationError('activation runtime publisher backup hash mismatch')
        run([
            '/usr/bin/python3', str(publisher_script),
            '--web-root', str(COCKPIT_STAGE_ROOT),
            '--rollback', str(safe_publisher_backup),
        ], cwd=backup, timeout=120)
    _restore_file(backup, state, 'registry', 'datasets.json', REGISTRY_PATH)
    _restore_file(backup, state, 'job', 'alpha-staging-job.json', JOB_PATH)
    marker = {
        'schema': STATE_SCHEMA,
        'status': 'rolled-back',
        'backup': str(backup),
        'rolled_back_at': utc_now(),
        'generated_evidence_preserved': True,
        'source_evidence_preserved': True,
        'fengus_evidence_preserved': True,
    }
    atomic_json(CURRENT_STATE, marker, mode=0o600)
    return marker


def rollback_last(repo: Path = EXPECTED_REPO) -> dict[str, Any]:
    current = read_json(CURRENT_STATE)
    backup = current.get('backup')
    if not isinstance(backup, str):
        raise ActivationError('current activation state has no rollback backup')
    return rollback(Path(backup), repo=repo)


def apply(repo: Path = EXPECTED_REPO) -> dict[str, Any]:
    if os.geteuid() != 0:
        raise ActivationError('--apply requires root')
    repo = _authorized_mutation_repo(repo)
    info = preflight(repo=repo)
    repo = Path(info['repo'])
    backup, backup_state = create_backup(BACKUP_ROOT, REGISTRY_PATH, JOB_PATH, info['dataset_state'], repo)
    publisher_backup: str | None = None
    try:
        prepare_synthetic_dataset(DATASET_PATH)
        source_before = dataset_state(DATASET_PATH)[1]
        enable_dataset(REGISTRY_PATH)
        job = create_job(repo)
        write_job(JOB_PATH, job)
        dispatch = dispatch_job(repo, JOB_PATH, REGISTRY_PATH, DATASET_ROOT, GENERATED_ROOT)
        source_after = dataset_state(DATASET_PATH)[1]
        if source_before != source_after:
            raise ActivationError('alpha-staging source changed during dispatch')
        fengus = run_fengus(job)
        update_fengus_status(GENERATED_PATH, fengus)
        acceptance = write_live_acceptance(GENERATED_PATH, DATASET_PATH, source_before, source_after, fengus)
        publication = publish(repo, GENERATED_PATH)
        publisher_backup = publication.get('backup') if isinstance(publication.get('backup'), str) else None
        backup_state.update({
            'completed_at': utc_now(),
            'job_id': job.get('job_id'),
            'run_id': dispatch.get('run_id'),
            'work_id': fengus.get('work_id'),
            'publisher_backup': publisher_backup,
        })
        atomic_json(backup / 'activation-state.json', backup_state, mode=0o600)
        current = {
            'schema': STATE_SCHEMA,
            'status': 'active-alpha-staging',
            'updated_at': utc_now(),
            'backup': str(backup),
            'job_id': job.get('job_id'),
            'run_id': dispatch.get('run_id'),
            'work_id': fengus.get('work_id'),
            'cockpit_stage': str(COCKPIT_STAGE_ROOT),
            'public_changes': False,
        }
        atomic_json(CURRENT_STATE, current, mode=0o600)
        return {
            'status': 'activated-alpha-staging',
            'backup': str(backup),
            'job_id': job.get('job_id'),
            'run_id': dispatch.get('run_id'),
            'work_id': fengus.get('work_id'),
            'acceptance': acceptance.get('result'),
            'cockpit_stage': str(COCKPIT_STAGE_ROOT),
            'publisher_backup': publisher_backup,
            'public_changes': False,
        }
    except Exception as exc:
        backup_state['failed_at'] = utc_now()
        backup_state['error_type'] = type(exc).__name__
        try:
            atomic_json(backup / 'activation-state.json', backup_state, mode=0o600)
        except Exception:
            pass
        try:
            if publisher_backup:
                run([
                    '/usr/bin/python3', str(repo / 'deploy/cookie_monster_runtime_publish.py'),
                    '--web-root', str(COCKPIT_STAGE_ROOT), '--rollback', publisher_backup,
                ], cwd=repo, timeout=120)
            _restore_file(backup, backup_state, 'registry', 'datasets.json', REGISTRY_PATH)
            _restore_file(backup, backup_state, 'job', 'alpha-staging-job.json', JOB_PATH)
        except Exception:
            pass
        raise


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description='Activate bounded Cookie Monster Alpha staging on Edge1')
    p.add_argument('--repo', type=Path, default=EXPECTED_REPO)
    mode = p.add_mutually_exclusive_group()
    mode.add_argument('--apply', action='store_true')
    mode.add_argument('--rollback', type=Path)
    mode.add_argument('--rollback-last', action='store_true')
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.rollback is not None:
            result = rollback(args.rollback, repo=args.repo)
        elif args.rollback_last:
            result = rollback_last(repo=args.repo)
        elif args.apply:
            result = apply(repo=args.repo)
        else:
            result = preflight(repo=args.repo)
    except ActivationError as exc:
        print(f'cookie-monster-edge1-activate: {exc}', file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
