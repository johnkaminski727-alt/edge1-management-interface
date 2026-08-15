"""Controlled automatic article ingestion for the WW.CX Edge1 relay."""

from __future__ import annotations

import contextlib
import fcntl
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from .config import IngestSourceConfig, RelayConfig
from .storage import CommsStore


class IngestError(RuntimeError):
    pass


@dataclass(frozen=True)
class Candidate:
    source_name: str
    source_item_id: str
    group: str
    subject: str
    body: str
    headers: dict[str, str]
    cursor: str | None = None


@contextlib.contextmanager
def _ingest_lock(cfg: RelayConfig) -> Iterator[bool]:
    if cfg.database_path == ':memory:':
        yield True
        return
    path = Path(cfg.database_path).with_name('ingest.lock')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+', encoding='utf-8') as handle:
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _git(source: IngestSourceConfig, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    if source.path is None:
        raise IngestError(f'git source {source.name} has no path')
    env = {
        'PATH': '/usr/bin:/bin',
        'LANG': 'C.UTF-8',
        'LC_ALL': 'C.UTF-8',
        'GIT_PAGER': 'cat',
        'GIT_OPTIONAL_LOCKS': '0',
        'HOME': '/nonexistent',
    }
    proc = subprocess.run(
        ['/usr/bin/git', '-c', f'safe.directory={source.path}', '-C', source.path, *args],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding='utf-8',
        errors='replace',
        env=env,
        timeout=15,
        check=False,
    )
    if check and proc.returncode != 0:
        raise IngestError(f'git source {source.name} command failed with exit {proc.returncode}')
    return proc


def _bootstrap_candidates(source: IngestSourceConfig, store: CommsStore) -> list[Candidate]:
    candidates: list[Candidate] = []
    for group in store.list_groups():
        name = str(group['name'])
        source_id = f'{name}:v1'
        if store.ingest_seen(source.name, source_id):
            continue
        moderated = bool(group['moderated'])
        body = '\n'.join(
            [
                f'Group: {name}',
                f'Description: {group["description"]}',
                f'Posting policy: {"moderated" if moderated else "authenticated members"}',
                f'Retention: {int(group["retention_days"])} days',
                '',
                'This group introduction was generated automatically by the WW.CX Edge1 Communications Relay.',
            ]
        )
        candidates.append(
            Candidate(
                source_name=source.name,
                source_item_id=source_id,
                group=name,
                subject=f'Welcome to {name}',
                body=body,
                headers={'X-WWCX-Source-Type': 'bootstrap'},
            )
        )
    return candidates


def _git_tip(source: IngestSourceConfig) -> str:
    return _git(source, 'rev-parse', '--verify', f'{source.ref}^{{commit}}').stdout.strip()


def _git_hashes(source: IngestSourceConfig, store: CommsStore) -> tuple[list[str], bool]:
    cursor = store.get_ingest_cursor(source.name)
    tip = _git_tip(source)
    if not cursor:
        raw = _git(source, 'rev-list', f'--max-count={source.initial_items}', tip).stdout.splitlines()
        return list(reversed([item.strip() for item in raw if item.strip()])), False
    ancestor = _git(source, 'merge-base', '--is-ancestor', cursor, tip, check=False).returncode == 0
    if ancestor:
        raw = _git(source, 'rev-list', '--reverse', f'{cursor}..{tip}').stdout.splitlines()
        hashes = [item.strip() for item in raw if item.strip()]
        return hashes[: source.scan_limit], False
    raw = _git(source, 'rev-list', f'--max-count={source.scan_limit}', tip).stdout.splitlines()
    hashes = list(reversed([item.strip() for item in raw if item.strip()]))
    return hashes, True


def _git_candidate(source: IngestSourceConfig, commit: str) -> Candidate:
    proc = _git(source, 'show', '-s', '--format=%H%x00%aI%x00%an%x00%s', commit)
    parts = proc.stdout.rstrip('\n').split('\x00', 3)
    if len(parts) != 4:
        raise IngestError(f'git source {source.name} returned malformed commit metadata')
    commit_id, authored_at, author_name, subject = (part.strip() for part in parts)
    if commit_id != commit:
        raise IngestError(f'git source {source.name} commit identity mismatch')
    source_url = f'{source.base_url}/commit/{commit_id}' if source.base_url else None
    body_lines = [
        f'Repository source: {source.name}',
        f'Commit: {commit_id}',
        f'Author: {author_name}',
        f'Committed: {authored_at}',
        f'Subject: {subject}',
    ]
    headers = {'X-WWCX-Source-Type': 'git', 'X-WWCX-Git-Commit': commit_id}
    if source_url:
        body_lines.extend(['', f'Source: {source_url}'])
        headers['X-WWCX-Source-URL'] = source_url
    return Candidate(
        source_name=source.name,
        source_item_id=commit_id,
        group=source.group or '',
        subject=f'{source.name}: {subject}',
        body='\n'.join(body_lines),
        headers=headers,
        cursor=commit_id,
    )


def _git_candidates(source: IngestSourceConfig, store: CommsStore) -> tuple[list[Candidate], bool, str]:
    hashes, rewritten = _git_hashes(source, store)
    tip = _git_tip(source)
    return [_git_candidate(source, commit) for commit in hashes], rewritten, tip


def run_ingestion(cfg: RelayConfig, store: CommsStore, *, dry_run: bool = False) -> dict[str, Any]:
    if not cfg.ingestion.enabled:
        return {'enabled': False, 'dry_run': dry_run, 'created': 0, 'deduplicated': 0, 'sources': []}
    with _ingest_lock(cfg) as locked:
        if not locked:
            return {'enabled': True, 'dry_run': dry_run, 'created': 0, 'deduplicated': 0, 'skipped': 'already_running', 'sources': []}
        remaining = cfg.ingestion.max_items_per_run
        created = 0
        deduplicated = 0
        source_results: list[dict[str, Any]] = []
        for source in cfg.ingestion.sources:
            if not source.enabled or remaining <= 0:
                continue
            rewritten = False
            tip: str | None = None
            if source.source_type == 'bootstrap':
                candidates = _bootstrap_candidates(source, store)
            elif source.source_type == 'git':
                candidates, rewritten, tip = _git_candidates(source, store)
            else:
                raise IngestError(f'unsupported source type: {source.source_type}')
            candidates = candidates[:remaining]
            source_created = 0
            source_deduplicated = 0
            preview: list[dict[str, str]] = []
            for candidate in candidates:
                if dry_run:
                    preview.append({'source_item_id': candidate.source_item_id, 'group': candidate.group, 'subject': candidate.subject})
                    continue
                result = store.post_ingested_article(
                    source_name=candidate.source_name,
                    source_item_id=candidate.source_item_id,
                    group_name=candidate.group,
                    subject=candidate.subject,
                    body=candidate.body,
                    server_name=cfg.server_name,
                    extra_headers=candidate.headers,
                    detail={'source_type': source.source_type},
                )
                if result['created']:
                    created += 1
                    source_created += 1
                else:
                    deduplicated += 1
                    source_deduplicated += 1
                if candidate.cursor:
                    store.set_ingest_cursor(source.name, candidate.cursor)
                remaining -= 1
                if remaining <= 0:
                    break
            if source.source_type == 'git' and not dry_run:
                if rewritten:
                    store.audit(None, 'ingest', 'source.history_rewritten', source.name, 'ok', {'tip': tip})
                if not candidates and tip and store.get_ingest_cursor(source.name) != tip:
                    store.set_ingest_cursor(source.name, tip)
            source_results.append(
                {
                    'name': source.name,
                    'type': source.source_type,
                    'created': source_created,
                    'deduplicated': source_deduplicated,
                    'candidates': len(candidates),
                    'history_rewritten': rewritten,
                    'preview': preview,
                }
            )
        result = {
            'enabled': True,
            'dry_run': dry_run,
            'created': created,
            'deduplicated': deduplicated,
            'remaining_budget': remaining,
            'sources': source_results,
        }
        if not dry_run:
            store.audit(None, 'ingest', 'run', cfg.server_name, 'ok', {'created': created, 'deduplicated': deduplicated, 'sources': len(source_results)})
        return result
