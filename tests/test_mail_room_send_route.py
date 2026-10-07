"""Mail Room POST /send rules (deploy/email/mail-room-send), exercised over HTTP with a fake gateway."""
import json
import sys
import tempfile
import threading
import types
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "deploy/email/mail-room-send/mailroom"))

# Stub the release modules mail_room_http imports but this test does not exercise.
for name, attrs in {
    "integrations": {}, "integrations.bigbird_mail": {},
    "integrations.bigbird_mail.tools": {"BigBirdMailTools": object, "MailToolConfig": object},
    "server.mail_room_features": {"MailRoomFeatures": object},
    "server.mail_security_updates": {"update_health": lambda: {}},
    "server.mail_room_access": {"admin_session": lambda h: True, "ACCESS_POLICY": {}},
    "server.mail_room_ava": {"AvaMailAssistant": object},
    "server.mail_room_security": {"SecurityStore": object, "required": lambda: False},
}.items():
    module = sys.modules.setdefault(name, types.ModuleType(name))
    for key, value in attrs.items():
        setattr(module, key, value)

from server import mail_room_http  # noqa: E402
from server.mail_room_send import MailSendError  # noqa: E402

KEY = "k" * 40
PREFIX = mail_room_http.PREFIX


class FakeMail:
    def status(self):
        return {"external_delivery_enabled": True}

    def prepare_draft(self, payload):
        return {"request": {"from_address": "john@ww.cx", "subject": payload["subject"], "recipients": payload["to"]}, "sender_selection": {"live_enabled": True}}


class FakeSender:
    def __init__(self):
        self.sent, self.fail = [], None

    def send(self, payload):
        if self.fail:
            raise MailSendError(self.fail)
        self.sent.append(payload)
        return {"delivery": {"message_id": "<m1@ww.cx>", "recipient_count": 1, "submitted_at": "2026-10-07T00:00:00+00:00", "provider": "edge1_local_mta"}, "body": "must not leak"}


class SendRouteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)  # Windows keeps sqlite files locked
        self.store = mail_room_http.DraftStore(Path(self.tmp.name) / "drafts.sqlite3")
        self.sender = FakeSender()

        class Features:  # minimal record_preparation, as in mail_room_features
            def __init__(inner, store):
                inner.store = store

            def record_preparation(inner, draft_id, result, updated):
                with inner.store.connect() as db:
                    db.execute("INSERT INTO preparations VALUES (?,?,?) ON CONFLICT(draft_id) DO UPDATE SET payload=excluded.payload,updated=excluded.updated",
                               (draft_id, json.dumps({"from_address": result["request"]["from_address"], "subject": result["request"]["subject"], "state": "prepared_not_sent"}), updated))

        handler = mail_room_http.make_handler(FakeMail(), self.store, KEY, Features(self.store), sender=self.sender)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()

    def post(self, route, data):
        request = urllib.request.Request(self.base + PREFIX + route, data=json.dumps(data).encode(), method="POST", headers={
            "X-Mail-Room-Proxy-Key": KEY, "Origin": "https://edge1.ww.cx", "X-Mail-Room-Request": "1", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read())

    def draft(self, subject="Hello"):
        status, saved = self.post("drafts", {"payload": {"to": ["a@example.com"], "subject": subject, "body": "Hi"}})
        self.assertEqual(status, 200)
        return saved["id"]

    def test_unprepared_draft_is_refused(self):
        status, body = self.post("send", {"id": self.draft(), "confirm": True})
        self.assertEqual(status, 400)
        self.assertEqual(self.sender.sent, [])

    def test_confirmation_is_required(self):
        draft_id = self.draft()
        self.post("prepare", {"id": draft_id})
        for data in ({"id": draft_id}, {"id": draft_id, "confirm": "yes"}, {"id": draft_id, "confirm": False}):
            self.assertEqual(self.post("send", data)[0], 400)
        self.assertEqual(self.sender.sent, [])

    def test_prepared_draft_sends_once_and_body_is_not_returned(self):
        draft_id = self.draft()
        self.post("prepare", {"id": draft_id})
        status, body = self.post("send", {"id": draft_id, "confirm": True})
        self.assertEqual(status, 200)
        self.assertTrue(body["sent"])
        self.assertNotIn("body", json.dumps(body))
        self.assertEqual(len(self.sender.sent), 1)
        self.assertEqual(self.post("send", {"id": draft_id, "confirm": True})[0], 400)
        self.assertEqual(len(self.sender.sent), 1)

    def test_editing_after_prepare_requires_a_new_prepare(self):
        draft_id = self.draft()
        self.post("prepare", {"id": draft_id})
        self.post("drafts", {"id": draft_id, "payload": {"to": ["b@example.com"], "subject": "Changed", "body": "Hi"}})
        self.assertEqual(self.post("send", {"id": draft_id, "confirm": True})[0], 400)
        self.assertEqual(self.sender.sent, [])

    def test_gateway_rejection_keeps_draft_sendable_after_fix(self):
        draft_id = self.draft()
        self.post("prepare", {"id": draft_id})
        self.sender.fail = "delivery_disabled"
        self.assertEqual(self.post("send", {"id": draft_id, "confirm": True})[0], 422)
        self.sender.fail = None
        self.assertEqual(self.post("send", {"id": draft_id, "confirm": True})[0], 200)

    def test_unknown_outcome_blocks_retry(self):
        draft_id = self.draft()
        self.post("prepare", {"id": draft_id})
        self.sender.fail = "outcome_unknown"
        self.assertEqual(self.post("send", {"id": draft_id, "confirm": True})[0], 409)
        self.sender.fail = None
        self.assertEqual(self.post("send", {"id": draft_id, "confirm": True})[0], 400)
        self.assertEqual(self.sender.sent, [])


if __name__ == "__main__":
    unittest.main()
