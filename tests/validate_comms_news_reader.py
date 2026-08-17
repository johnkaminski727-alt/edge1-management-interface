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
            source_item_id='<root@example.test>',
            group_name='wwcx.test',
            author='Example Author <author@example.test>',
            subject='Reader validation root',
            body='This is the stored root article body.',
            server_name='edge1.ww.cx',
            extra_headers={
                'X-WWCX-Source-Type': 'nntp',
                'X-WWCX-Upstream-Server': 'news.example.test',
                'X-WWCX-Upstream-Group': 'comp.lang.python',
                'X-WWCX-Upstream-Message-ID': '<root@example.test>',
                'X-WWCX-Upstream-Article-Number': '42',
                'X-WWCX-Upstream-Content-Type': 'text/plain',
            },
        )
        reply = store.post_ingested_article(
            source_name='eternal.comp.lang.python',
            source_item_id='<reply@example.test>',
            group_name='wwcx.test',
            author='Reply Author <reply@example.test>',
            subject='Re: Reader validation root',
            body='This is the stored reply body.',
            server_name='edge1.ww.cx',
            extra_headers={
                'X-WWCX-Source-Type': 'nntp',
                'X-WWCX-Upstream-Server': 'news.example.test',
                'X-WWCX-Upstream-Group': 'comp.lang.python',
                'X-WWCX-Upstream-Message-ID': '<reply@example.test>',
                'X-WWCX-Upstream-Article-Number': '43',
                'X-WWCX-Upstream-Content-Type': 'text/plain',
                'X-WWCX-Upstream-References': '<root@example.test>',
            },
        )
        native = store.post_article(
            group_name='wwcx.test',
            author='Local User <local@users.ww.cx>',
            account=None,
            subject='Native reader note',
            body='Local-only article body.',
            message_id='<native@example.test>',
            server_name='edge1.ww.cx',
        )
        store.set_ingest_cursor('eternal.comp.lang.python', '43')
        cfg = RelayConfig(database_path=str(root / 'comms.sqlite3'))
        server = ControlServer(('127.0.0.1', 0), cfg, store, web_root=web)
        thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': 0.02}, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{server.server_address[1]}'
        try:
            groups = get_json(base, '/api/comms/news/groups')
            check(any(item['name'] == 'wwcx.test' and item['count'] == 3 for item in groups), 'group count missing')

            first_page = get_json(base, '/api/comms/news/groups/wwcx.test/articles?limit=1&offset=0')
            check(first_page['group']['name'] == 'wwcx.test', 'group detail missing')
            check(first_page['pagination']['total'] == 3, 'pagination total incorrect')
            check(first_page['pagination']['returned'] == 1, 'page size not applied')
            check(first_page['pagination']['has_next'] is True, 'next page not advertised')
            check(first_page['pagination']['next_offset'] == 1, 'next offset incorrect')
            check(first_page['articles'][0]['id'] == native['id'], 'newest article not returned first')
            check('body' not in first_page['articles'][0], 'article list leaked body payload')

            second_page = get_json(base, '/api/comms/news/groups/wwcx.test/articles?limit=1&offset=1')
            check(second_page['articles'][0]['id'] == reply['article_id'], 'offset pagination returned wrong article')
            check(second_page['pagination']['has_previous'] is True, 'previous page not advertised')
            check(second_page['pagination']['previous_offset'] == 0, 'previous offset incorrect')

            external = get_json(base, '/api/comms/news/groups/wwcx.test/articles?limit=20&source=eternal.comp.lang.python')
            check(external['pagination']['total'] == 2, 'source filter did not isolate imported articles')
            check(all(item['source_name'] == 'eternal.comp.lang.python' for item in external['articles']), 'source filter leaked another source')
            by_id = {item['id']: item for item in external['articles']}
            check(by_id[first['article_id']]['thread_key'] == '<root@example.test>', 'root thread key incorrect')
            check(by_id[first['article_id']]['thread_depth'] == 0, 'root thread depth incorrect')
            check(by_id[reply['article_id']]['thread_key'] == '<root@example.test>', 'reply did not join root thread')
            check(by_id[reply['article_id']]['thread_parent'] == '<root@example.test>', 'reply parent incorrect')
            check(by_id[reply['article_id']]['thread_depth'] == 1, 'reply depth incorrect')

            native_only = get_json(base, '/api/comms/news/groups/wwcx.test/articles?source=native')
            check(native_only['pagination']['total'] == 1, 'native source filter count incorrect')
            check(native_only['articles'][0]['id'] == native['id'], 'native filter returned wrong article')
            check(native_only['articles'][0]['source_name'] is None, 'native filter returned ingested provenance')

            search = get_json(base, '/api/comms/news/groups/wwcx.test/articles?q=Reply&source=eternal.comp.lang.python')
            check(search['pagination']['total'] == 1, 'combined search and source filter failed')
            check(search['articles'][0]['id'] == reply['article_id'], 'search returned wrong article')

            source_counts = {item['source_name']: item['count'] for item in external['source_counts']}
            check(source_counts['eternal.comp.lang.python'] == 2, 'external source count missing')
            check(source_counts[None] == 1, 'native source count missing')

            article = get_json(base, f"/api/comms/news/articles/{first['article_id']}")
            check(article['body'] == 'This is the stored root article body.', 'article body missing')
            check(article['source_item_id'] == '<root@example.test>', 'source item provenance missing')
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

    print('PASS validate_comms_news_reader threaded pagination and source filters')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
