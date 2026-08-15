#!/usr/bin/env python3
"""Validate controlled automatic article ingestion for the Edge1 relay."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVER_ROOT = REPO_ROOT / 'server'
sys.path.insert(0, str(SERVER_ROOT))

from edge1_comms.config import ConfigError, config_from_dict
from edge1_comms.ingest import run_ingestion
from edge1_comms.storage import CommsStore


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def git(path: Path, *args: str) -> str:
    proc = subprocess.run(['git', '-C', str(path), *args], check=True, stdout=subprocess.PIPE, text=True)
    return proc.stdout.strip()


def commit(repo: Path, name: str, body: str) -> str:
    target = repo / name
    target.write_text(body, encoding='utf-8')
    git(repo, 'add', name)
    git(repo, 'commit', '-m', f'Update {name}')
    return git(repo, 'rev-parse', 'HEAD')


def payload(db: Path, repo: Path) -> dict[str, object]:
    return {
        'server_name': 'edge1.ww.cx',
        'network_name': 'WW.CX',
        'database_path': str(db),
        'network_exposure': {'enabled': False},
        'listeners': {
            'irc': {'enabled': True, 'host': '127.0.0.1', 'port': 16667, 'tls': False},
            'nntp': {'enabled': True, 'host': '127.0.0.1', 'port': 1119, 'tls': False},
            'control': {'enabled': True, 'host': '127.0.0.1', 'port': 8100, 'tls': False},
        },
        'ingestion': {
            'enabled': True,
            'startup_delay_seconds': 0,
            'interval_seconds': 60,
            'max_items_per_run': 20,
            'sources': [
                {'type': 'bootstrap', 'name': 'wwcx-bootstrap', 'enabled': True, 'initial_items': 8, 'scan_limit': 100},
                {
                    'type': 'git',
                    'name': 'edge1-repository',
                    'enabled': True,
                    'group': 'wwcx.projects.edge1',
                    'path': str(repo),
                    'ref': 'main',
                    'base_url': 'https://example.test/edge1',
                    'initial_items': 2,
                    'scan_limit': 100,
                },
            ],
        },
    }


def validate_config_rejections(base: dict[str, object]) -> None:
    bad = json.loads(json.dumps(base)); bad['ingestion']['sources'][1]['path'] = 'relative/repo'
    try: config_from_dict(bad); raise AssertionError('relative git path accepted')
    except ConfigError: pass
    bad = json.loads(json.dumps(base)); bad['ingestion']['sources'][1]['base_url'] = 'http://example.test/edge1'
    try: config_from_dict(bad); raise AssertionError('non-HTTPS source URL accepted')
    except ConfigError: pass
    bad = json.loads(json.dumps(base)); bad['ingestion']['sources'][1]['type'] = 'rss'
    try: config_from_dict(bad); raise AssertionError('unsupported source type accepted')
    except ConfigError: pass


def main() -> int:
    with tempfile.TemporaryDirectory(prefix='edge1-ingest-') as name:
        tmp = Path(name); repo = tmp / 'repo'; repo.mkdir()
        git(repo, 'init', '-b', 'main'); git(repo, 'config', 'user.name', 'Edge1 Test'); git(repo, 'config', 'user.email', 'edge1@example.test')
        first = commit(repo, 'one.txt', 'one\n'); commit(repo, 'two.txt', 'two\n'); third = commit(repo, 'three.txt', 'three\n')
        config_payload = payload(tmp / 'comms.sqlite3', repo); validate_config_rejections(config_payload)
        cfg = config_from_dict(config_payload); store = CommsStore(cfg.database_path)

        preview = run_ingestion(cfg, store, dry_run=True)
        check(preview['dry_run'] is True and preview['created'] == 0, 'dry-run mutated state')
        check(store.stats()['articles'] == 0, 'dry-run created articles')

        first_run = run_ingestion(cfg, store)
        check(first_run['created'] == 9, f'unexpected first-run count: {first_run}')
        check(store.ingest_count('wwcx-bootstrap') == 7, 'bootstrap did not create one introduction per group')
        check(store.ingest_count('edge1-repository') == 2, 'git initial import count wrong')
        check(store.get_ingest_cursor('edge1-repository') == third, 'git cursor did not advance to newest imported commit')
        edge_articles = store.articles_for_group('wwcx.projects.edge1')
        git_articles = [row for row in edge_articles if row['headers'].get('X-WWCX-Source') == 'edge1-repository']
        check(len(git_articles) == 2, 'git articles missing')
        check(all(row['headers'].get('X-WWCX-Automated') == 'yes' for row in git_articles), 'automated header missing')
        check(git_articles[-1]['headers'].get('X-WWCX-Source-URL', '').endswith(third), 'source URL missing commit id')
        check(first not in [row['headers'].get('X-WWCX-Git-Commit') for row in git_articles], 'initial import exceeded configured lookback')

        second_run = run_ingestion(cfg, store)
        check(second_run['created'] == 0, 'dedupe failed on unchanged sources')
        check(store.stats()['articles'] == 9, 'unchanged run changed article count')

        fourth = commit(repo, 'four.txt', 'four\n')
        third_run = run_ingestion(cfg, store)
        check(third_run['created'] == 1, f'new git commit not ingested: {third_run}')
        check(store.get_ingest_cursor('edge1-repository') == fourth, 'cursor did not advance after new commit')
        check(store.stats()['articles'] == 10, 'new commit did not create exactly one article')
        with store.connect() as conn: message_ids = [row[0] for row in conn.execute('SELECT message_id FROM articles').fetchall()]
        check(len(message_ids) == len(set(message_ids)), 'ingested message ids are not unique')
        check(store.stats()['ingested_items'] == 10, 'ingestion stats incorrect')

    print('PASS validate_comms_ingest controlled automatic article ingestion')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
