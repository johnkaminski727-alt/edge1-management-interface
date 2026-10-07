import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from http.server import ThreadingHTTPServer
from server.mail_room_http import DraftStore, make_handler, PREFIX


class FakeMail:
    def correspondence_status(self):
        return {"ready": True}
    def correspondence_search(self, **filters):
        return {"messages": [], "filters": filters}
    def correspondence_thread(self, **filters):
        return {"thread": {"messages": [{"body_text": "<script>untrusted</script>"}]}}
    def prepare_draft(self, payload):
        return {"preparation_api": {"delivery_status": "prepared_not_sent"}, "external_delivery_enabled": False}


class MailRoomTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'drafts.sqlite3'
        self.store = DraftStore(self.path)
        self.key = 'k' * 48
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(FakeMail(), self.store, self.key))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(); self.tmp.cleanup()
    def request(self, path, data=None, headers=None):
        h = {"X-Mail-Room-Proxy-Key": self.key}
        if data is not None:
            h.update({"Content-Type": "application/json", "Origin": "https://edge1.ww.cx", "X-Mail-Room-Request": "1"})
        h.update(headers or {})
        req = urllib.request.Request('http://127.0.0.1:%s%s%s' % (self.server.server_port, PREFIX, path), data=None if data is None else json.dumps(data).encode(), headers=h)
        try:
            with urllib.request.urlopen(req) as r: return r.status, json.load(r)
        except urllib.error.HTTPError as e: return e.code, json.load(e)
    def test_proxy_and_csrf_boundaries(self):
        self.assertEqual(self.request('status', headers={"X-Mail-Room-Proxy-Key": ""})[0], 403)
        for headers in [{"Origin": "https://evil.example"}, {"X-Mail-Room-Request": ""}, {"Content-Type": "text/plain"}]:
            self.assertEqual(self.request('drafts', {"payload": {}}, headers)[0], 403)
        self.assertEqual(self.store.list(), [])
    def test_persistence_and_prepare_without_delivery(self):
        status, saved = self.request('drafts', {"payload": {"subject": "Review", "body": "Private text", "to": ["person@example.test"]}})
        self.assertEqual(status, 200)
        restored = DraftStore(self.path).get(saved['id'])
        self.assertEqual(restored['payload']['body'], 'Private text')
        status, prepared = self.request('prepare', {"id": saved['id']})
        self.assertEqual(status, 200)
        self.assertFalse(prepared['external_delivery_enabled'])
        self.assertEqual(self.request('send', {})[0], 404)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
    def test_search_and_payload_limits(self):
        self.assertEqual(self.request('messages?offset=10001')[0], 400)
        self.assertEqual(self.request('messages?q=' + 'a'*201)[0], 400)
        self.assertEqual(self.request('messages?q=a&q=b')[0], 400)
        self.assertEqual(self.request('drafts', {"payload": {"action_token": "forbidden"}})[0], 400)
        self.assertEqual(self.request('drafts', {"payload": {"body": 'x'*100001}})[0], 400)
        status, data = self.request('messages?q=literal%25')
        self.assertEqual(status, 200)
        self.assertEqual(data['filters']['query'], 'literal%')

if __name__ == '__main__': unittest.main()
