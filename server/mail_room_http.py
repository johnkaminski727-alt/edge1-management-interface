"""Private browser bridge. nginx must authenticate sessions before forwarding.

The proxy key is distinct from the gateway signing key. Neither reaches JS.
Mail is plain text; drafts are private local records, never delivery commands.
"""
from __future__ import annotations

import argparse
import hmac
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from integrations.bigbird_mail.tools import BigBirdMailTools, MailToolConfig

PREFIX = "/edge1-ops/mail-room/api/"
FIELDS = {"to", "cc", "bcc", "subject", "body", "message_class", "signer_name", "signer_title", "mailing_address", "original_recipient", "identity_hint", "thread_id", "source_message_id", "in_reply_to", "references"}


class DraftStore:
    def __init__(self, path):
        self.path = str(path)
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS drafts (id TEXT PRIMARY KEY, payload TEXT NOT NULL, updated TEXT NOT NULL)")
        os.chmod(self.path, 0o600)

    def connect(self):
        return sqlite3.connect(self.path, timeout=5)

    def list(self):
        with self.connect() as db:
            return [{"id": row[0], "subject": json.loads(row[1]).get("subject", ""), "updated": row[2]} for row in db.execute("SELECT id,payload,updated FROM drafts ORDER BY updated DESC LIMIT 100")]

    def get(self, key):
        with self.connect() as db:
            row = db.execute("SELECT payload,updated FROM drafts WHERE id=?", (key,)).fetchone()
        if not row:
            raise KeyError(key)
        return {"id": key, "payload": json.loads(row[0]), "updated": row[1]}

    def save(self, payload):
        if not isinstance(payload, dict) or set(payload) - {"id", "payload"}:
            raise ValueError("Invalid draft")
        data = payload.get("payload")
        if not isinstance(data, dict) or set(data) - FIELDS:
            raise ValueError("Invalid draft fields")
        for key, value in data.items():
            if key in {"to", "cc", "bcc", "references"}:
                if not isinstance(value, list) or len(value) > 50 or any(not isinstance(v, str) or len(v) > 998 for v in value):
                    raise ValueError("Invalid address or reference list")
            elif not isinstance(value, str) or len(value) > (100000 if key == "body" else 1000):
                raise ValueError("Draft field too long")
        key = payload.get("id") or str(uuid.uuid4())
        if not isinstance(key, str) or str(uuid.UUID(key)) != key:
            raise ValueError("Invalid draft ID")
        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as db:
            db.execute("INSERT INTO drafts VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload,updated=excluded.updated", (key, json.dumps(data), now))
        return self.get(key)


def make_handler(mail, store, proxy_key):
    if len(proxy_key) < 32:
        raise ValueError("Mail Room proxy key is required")

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(15)

        def log_message(self, *args):
            pass  # No mail content, IDs, search queries or cookies in access logs.

        def reply(self, status, data):
            raw = json.dumps(data).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def authorized(self, mutation=False):
            valid = hmac.compare_digest(self.headers.get("X-Mail-Room-Proxy-Key", ""), proxy_key)
            if mutation:
                valid = valid and self.headers.get("Origin") == "https://edge1.ww.cx" and self.headers.get("X-Mail-Room-Request") == "1" and self.headers.get("Content-Type", "").split(";")[0] == "application/json"
            if not valid:
                self.reply(403, {"error": "Access denied"})
            return valid

        def do_GET(self):
            if not self.authorized():
                return
            parsed = urlsplit(self.path)
            if not parsed.path.startswith(PREFIX):
                self.reply(404, {"error": "Not found"}); return
            route = parsed.path[len(PREFIX):]
            try:
                if route == "status":
                    data = {"correspondence": mail.correspondence_status(), "provider_connected": os.getenv("WWCX_MAIL_PROVIDER_CONNECTED") == "true", "send_enabled": False}
                elif route == "messages":
                    q = parse_qs(parsed.query)
                    if set(q) - {"q", "recipient", "offset"} or any(len(v) != 1 for v in q.values()):
                        raise ValueError("Invalid search")
                    query = q.get("q", [""])[0]
                    offset = int(q.get("offset", [0])[0])
                    recipient = q.get("recipient", [None])[0]
                    if len(query) > 200 or any(ord(c) < 32 for c in query) or not 0 <= offset <= 10000 or (recipient is not None and (len(recipient) > 320 or "@" not in recipient)):
                        raise ValueError("Invalid search")
                    data = mail.correspondence_search(query=query, recipient=recipient, offset=offset, limit=25)
                elif route.startswith("message/"):
                    data = mail.correspondence_message(message_id=unquote(route[8:]))
                elif route.startswith("thread/"):
                    data = mail.correspondence_thread(thread_id=unquote(route[7:]))
                elif route == "drafts":
                    data = {"drafts": store.list()}
                elif route.startswith("draft/"):
                    data = store.get(route[6:])
                else:
                    self.reply(404, {"error": "Not found"}); return
                self.reply(200, data)
            except KeyError:
                self.reply(404, {"error": "Draft not found"})
            except (ValueError, TypeError):
                self.reply(400, {"error": "Invalid request"})
            except Exception:
                self.reply(503, {"error": "Mail service unavailable. Your saved drafts remain local."})

        def do_POST(self):
            if not self.authorized(mutation=True):
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 1 <= length <= 150000:
                    self.reply(413, {"error": "Draft too large"}); return
                data = json.loads(self.rfile.read(length))
                if self.path == PREFIX + "drafts":
                    result = store.save(data)
                elif self.path == PREFIX + "prepare":
                    if not isinstance(data, dict) or set(data) != {"id"}:
                        raise ValueError("Draft ID required")
                    result = mail.prepare_draft(store.get(data["id"])["payload"])
                else:
                    self.reply(404, {"error": "Not found"}); return
                self.reply(200, result)
            except (ValueError, TypeError, KeyError):
                self.reply(400, {"error": "Invalid draft request"})
            except Exception:
                self.reply(422, {"error": "Preparation could not complete. Check required signature, sender and recipient fields. Draft remains saved; nothing sent."})

    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8117)
    args = parser.parse_args()
    os.umask(0o077)
    mail = BigBirdMailTools(MailToolConfig.from_environment())
    handler = make_handler(mail, DraftStore(args.database), os.environ["WWCX_MAIL_ROOM_PROXY_KEY"])
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    server.timeout = 10
    server.serve_forever()


if __name__ == "__main__":
    main()
