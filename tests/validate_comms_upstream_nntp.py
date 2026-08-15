#!/usr/bin/env python3
"""Validate selective outbound-only NNTP ingestion without external network access."""

from __future__ import annotations

import io
import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVER_ROOT = REPO_ROOT / 'server'
sys.path.insert(0, str(SERVER_ROOT))

import edge1_comms.ingest as ingest_module
import edge1_comms.upstream_nntp as upstream_module
from edge1_comms.config import ConfigError, config_from_dict, sanitized_config
from edge1_comms.ingest import run_ingestion
from edge1_comms.storage import CommsStore
from edge1_comms.upstream_nntp import PullResult, UpstreamArticle


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def source_payload(db: Path) -> dict[str, object]:
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
            'max_items_per_run': 10,
            'sources': [
                {
                    'type': 'nntp',
                    'name': 'eternal.comp.lang.python',
                    'enabled': True,
                    'host': 'news.eternal-september.org',
                    'port': 563,
                    'tls': True,
                    'upstream_group': 'comp.lang.python',
                    'group': 'usenet.comp.lang.python',
                    'credential_file': '/etc/wwcx/credentials/eternal-september.json',
                    'create_group': True,
                    'retention_days': 3650,
                    'max_article_bytes': 131072,
                    'initial_items': 8,
                    'scan_limit': 100,
                }
            ],
        },
    }


def validate_config(base: dict[str, object]) -> None:
    cfg = config_from_dict(base)
    safe = sanitized_config(cfg)
    source = safe['ingestion']['sources'][0]
    check(source['host'] == 'news.eternal-september.org', 'sanitized upstream host missing')
    check(source['credential_file_configured'] is True, 'credential-file configured flag missing')
    check('credential_file' not in source, 'credential path leaked through sanitized config')

    bad = json.loads(json.dumps(base)); bad['ingestion']['sources'][0]['tls'] = False
    try: config_from_dict(bad); raise AssertionError('plaintext upstream NNTP accepted')
    except ConfigError: pass
    bad = json.loads(json.dumps(base)); bad['ingestion']['sources'][0]['host'] = '127.0.0.1'
    try: config_from_dict(bad); raise AssertionError('IP-literal upstream host accepted')
    except ConfigError: pass
    bad = json.loads(json.dumps(base)); bad['ingestion']['sources'][0]['credential_file'] = 'relative/secret.json'
    try: config_from_dict(bad); raise AssertionError('relative credential file accepted')
    except ConfigError: pass
    bad = json.loads(json.dumps(base)); bad['ingestion']['sources'][0]['max_article_bytes'] = 20_000_000
    try: config_from_dict(bad); raise AssertionError('oversized upstream article limit accepted')
    except ConfigError: pass


def validate_ingestion(base: dict[str, object]) -> None:
    cfg = config_from_dict(base)
    store = CommsStore(cfg.database_path)
    source = cfg.ingestion.sources[0]
    originals = (
        UpstreamArticle(100, '<one@example.test>', 'First upstream subject', 'Alice <alice@example.test>', 'Sat, 15 Aug 2026 18:00:00 +0000', '', 'First body\n', 'text/plain'),
        UpstreamArticle(101, '<two@example.test>', 'Second upstream subject', 'Bob <bob@example.test>', 'Sat, 15 Aug 2026 18:01:00 +0000', '<one@example.test>', 'Second body\n', 'text/plain'),
    )

    old_pull = ingest_module.pull_articles
    def fake_pull(source_arg, cursor, *, limit, seen):
        available = tuple(item for item in originals if not seen(item.message_id))[:limit]
        return PullResult(available, '101', False, 2, len(originals) - len(available))
    ingest_module.pull_articles = fake_pull
    try:
        preview = run_ingestion(cfg, store, dry_run=True)
        check(preview['created'] == 0 and preview['sources'][0]['candidates'] == 2, 'NNTP dry-run preview incorrect')
        check(store.group_info(source.group or '') is None, 'NNTP dry-run created local group')

        first = run_ingestion(cfg, store)
        check(first['created'] == 2, f'NNTP first run created wrong count: {first}')
        info = store.group_info('usenet.comp.lang.python')
        check(info is not None and info['retention_days'] == 3650, 'mapped upstream group was not created correctly')
        check(store.get_ingest_cursor(source.name) == '101', 'NNTP article cursor did not advance')
        rows = store.articles_for_group('usenet.comp.lang.python')
        check(len(rows) == 2, 'mapped upstream articles missing')
        check(rows[0]['author'].startswith('Alice'), 'upstream author was not preserved')
        check(rows[0]['headers'].get('X-WWCX-Upstream-Message-ID') == '<one@example.test>', 'upstream Message-ID provenance missing')
        check(rows[1]['headers'].get('X-WWCX-Upstream-References') == '<one@example.test>', 'upstream References provenance missing')
        check(all(row['headers'].get('X-WWCX-Automated') == 'yes' for row in rows), 'automated provenance missing')
        check(all(row['message_id'] not in {'<one@example.test>', '<two@example.test>'} for row in rows), 'upstream Message-ID reused as local identity')

        second = run_ingestion(cfg, store)
        check(second['created'] == 0, 'NNTP dedupe failed on unchanged upstream articles')
        check(store.stats()['articles'] == 2, 'NNTP repeat run changed article count')
    finally:
        ingest_module.pull_articles = old_pull


def validate_protocol_parser(base: dict[str, object], credential_path: Path) -> None:
    payload = json.loads(json.dumps(base))
    payload['ingestion']['sources'][0]['credential_file'] = str(credential_path)
    cfg = config_from_dict(payload)
    source = cfg.ingestion.sources[0]

    article = (
        b'From: Carol <carol@example.test>\r\n'
        b'Subject: Scripted upstream article\r\n'
        b'Date: Sat, 15 Aug 2026 18:02:00 +0000\r\n'
        b'Message-ID: <scripted@example.test>\r\n'
        b'Content-Type: text/plain; charset=utf-8\r\n'
        b'\r\n'
        b'Hello from scripted NNTP.\r\n'
    )
    responses = [
        b'200 scripted.example.test ready\r\n',
        b'381 password required\r\n',
        b'281 authentication accepted\r\n',
        b'211 1 42 42 comp.lang.python\r\n',
        b'220 42 <scripted@example.test> article follows\r\n',
        *[line + b'\r\n' for line in article.rstrip(b'\r\n').split(b'\r\n')],
        b'.\r\n',
        b'205 closing connection\r\n',
    ]

    class ScriptedWriter(io.BytesIO):
        def close(self):
            pass

    class ScriptedSocket:
        def __init__(self):
            self.reader = io.BytesIO(b''.join(responses))
            self.writer = ScriptedWriter()
        def settimeout(self, value):
            pass
        def makefile(self, mode):
            return self.reader if 'r' in mode else self.writer
        def close(self):
            pass

    class ScriptedContext:
        def wrap_socket(self, raw, server_hostname=None):
            return raw

    scripted = ScriptedSocket()
    old_connect = upstream_module.socket.create_connection
    old_context = upstream_module.ssl.create_default_context
    upstream_module.socket.create_connection = lambda address, timeout=None: scripted
    upstream_module.ssl.create_default_context = lambda: ScriptedContext()
    try:
        result = upstream_module.pull_articles(source, None, limit=1, seen=lambda message_id: False)
    finally:
        upstream_module.socket.create_connection = old_connect
        upstream_module.ssl.create_default_context = old_context

    check(len(result.articles) == 1, 'scripted NNTP reader did not return article')
    check(result.articles[0].message_id == '<scripted@example.test>', 'scripted NNTP Message-ID parse failed')
    check(result.cursor == '42', 'scripted NNTP cursor incorrect')
    written = scripted.writer.getvalue()
    check(b'AUTHINFO USER example-user\r\n' in written, 'NNTP username authentication command missing')
    check(b'AUTHINFO PASS example-password\r\n' in written, 'NNTP password authentication command missing')
    check(b'GROUP comp.lang.python\r\n' in written, 'NNTP GROUP command missing')
    check(b'ARTICLE 42\r\n' in written, 'NNTP ARTICLE command missing')


def main() -> int:
    with tempfile.TemporaryDirectory(prefix='edge1-upstream-nntp-') as name:
        tmp = Path(name)
        base = source_payload(tmp / 'comms.sqlite3')
        validate_config(base)
        validate_ingestion(base)
        credential = tmp / 'upstream.json'
        credential.write_text(json.dumps({'username': 'example-user', 'password': 'example-password'}), encoding='utf-8')
        validate_protocol_parser(source_payload(tmp / 'protocol.sqlite3'), credential)
    print('PASS validate_comms_upstream_nntp selective TLS upstream ingestion')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
