#!/usr/bin/env python3
"""Validate the private read-only WW.CX Communications Relay News Reader API."""
from __future__ import annotations

import json
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVER_ROOT = REPO_ROOT / 'server'
sys.path.insert(0, str(SERVER_ROOT))

from edge1_comms.config import RelayConfig
from edge1_comms.control import ControlServer
from edge1_comms.storage import CommsStore


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def get_json(base: str, path: str) -> object:
    with urllib.request.urlopen(base + path, timeout=2) as response:
        check(response.status == 200, f'{path} returned {response.status}')
        return json.loads(response.read())


def main() -> int:
    with tempfile.TemporaryDirectory(prefix='edge1-comms-news-') as name:
        root = Path(name)
        web = root / 'web'
        web.mkdir()
        (web / 'index.html').write_text('ok', encoding='utf-8')
        store = CommsStore(root / 'comms.sqlite3', password_iterations=100000)
        first = store.post_ingested_article(
            source_name='eternal.comp.lang.python',
            source_item_id='<upstream@example.test>',
            group_name='wwcx.test',
            author='Example Author <author@example.test>',
            subject='Reader validation article',
            body='This is the stored article body.',
            server_name='edge1.ww.cx',
            extra_headers={
                'X-WWCX-Source-Type': 'nntp',
                'X-WWCX-Upstream-Server': 'news.example.test',
                'X-WWCX-Upstream-Group': 'comp.lang.python',
                'X-WWCX-Upstream-Message-ID': '<upstream@example.test>',
                'X-WWCX-Upstream-Article-Number': '42',
                'X-WWCX-Upstream-Content-Type': 'text/plain',
            },
        )
        store.set_ingest_cursor('eternal.comp.lang.python', '42')
        cfg = RelayConfig(database_path=str(root / 'comms.sqlite3'))
        server = ControlServer(('127.0.0.1', 0), cfg, store, web_root=web)
        thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': 0.02}, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{server.server_address[1]}'
        try:
            groups = get_json(base, '/api/comms/news/groups')
            check(any(item['name'] == 'wwcx.test' and item['count'] == 1 for item in groups), 'group count missing')

            listing = get_json(base, '/api/comms/news/groups/wwcx.test/articles?limit=20&q=validation')
            check(listing['group']['name'] == 'wwcx.test', 'group detail missing')
            check(len(listing['articles']) == 1, 'article search did not return one row')
            summary = listing['articles'][0]
            check('body' not in summary, 'article list leaked body payload')
            check(summary['source_name'] == 'eternal.comp.lang.python', 'summary provenance missing')

            article = get_json(base, f"/api/comms/news/articles/{first['article_id']}")
            check(article['body'] == 'This is the stored article body.', 'article body missing')
            check(article['source_item_id'] == '<upstream@example.test>', 'source item provenance missing')
            check(article['headers']['X-WWCX-Upstream-Article-Number'] == '42', 'upstream provenance missing')

            sources = get_json(base, '/api/comms/news/sources')
            check(isinstance(sources, list), 'sources endpoint did not return a list')

            request = urllib.request.Request(base + '/api/comms/news/groups', method='POST', data=b'{}')
            try:
                urllib.request.urlopen(request, timeout=2)
                raise AssertionError('read-only API accepted POST')
            except urllib.error.HTTPError as error:
                check(error.code == 405, f'POST returned {error.code}, expected 405')
                payload = json.loads(error.read())
                check(payload['error'] == 'read_only_control_api', 'POST did not return read-only error')
        finally:
            server.shutdown()
            server.server_close()
            thread.join(2)
            check(not thread.is_alive(), 'control server did not stop')

    print('PASS validate_comms_news_reader private read-only browser')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
