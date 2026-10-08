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
from server.mail_room_features import MailRoomFeatures
from server.mail_security_updates import update_health
from server.mail_room_access import admin_session, ACCESS_POLICY
from server.mail_room_ava import AvaMailAssistant
from server.mail_room_security import SecurityStore, required as security_required
from server.mail_room_send import MailRoomSendClient, MailSendError
import hashlib
import time

PREFIX = "/edge1-ops/mail-room/api/"
FIELDS = {"to", "cc", "bcc", "subject", "body", "message_class", "signer_name", "signer_title", "mailing_address", "original_recipient", "identity_hint", "thread_id", "source_message_id", "in_reply_to", "references", "unsubscribe_url"}


class DraftStore:
    def __init__(self, path):
        self.path = str(path)
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS preparations (draft_id TEXT PRIMARY KEY, payload TEXT NOT NULL, updated TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS drafts (id TEXT PRIMARY KEY, payload TEXT NOT NULL, updated TEXT NOT NULL)")
        os.chmod(self.path, 0o600)

    def connect(self):
        return sqlite3.connect(self.path, timeout=5, uri=True)

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
            db.execute("DELETE FROM preparations WHERE draft_id=?", (key,))
        return self.get(key)


def make_handler(mail, store, proxy_key, features=None, assistant=None, security=None, session_check=None, sender=None, ava_read_key=None):
    if len(proxy_key) < 32:
        raise ValueError("Mail Room proxy key is required")

    if ava_read_key is not None and len(ava_read_key) < 32:
        raise ValueError("Ava Mail Room read key is invalid")

    def ava_messages(query):
        if not features:
            raise ValueError("Mail Room features unavailable")
        allowed = {"q", "recipient", "domain", "folder", "room", "tag"}
        if set(query) - allowed:
            raise ValueError("Invalid Ava mail filters")
        listing = features.messages(query)
        folder = query.get("folder", ["inbox"])[0]
        include_body = folder not in {"quarantine", "junk", "pending"}
        messages = []
        for item in listing.get("messages", [])[:8]:
            safe = {k: item.get(k) for k in (
                "message_id", "thread_id", "sender", "recipients", "subject", "occurred_at",
                "direction", "is_read", "archived", "tags", "provenance",
            )}
            safe["body_excerpt"] = ""
            if include_body:
                try:
                    record = mail.correspondence_message(message_id=item["message_id"])
                    message = record.get("message", record) if isinstance(record, dict) else {}
                    body = message.get("body_text", "") if isinstance(message, dict) else ""
                    if isinstance(body, str):
                        safe["body_excerpt"] = body[:2400]
                except Exception:
                    pass
            messages.append(safe)
        return {
            "contract": "wwcx.ava-mail-room-read.v1",
            "messages": messages,
            "count": len(messages),
            "has_more": bool(listing.get("has_more")),
            "folder": folder,
            "content_is_untrusted": True,
            "send_authorized": False,
            "mutation_authorized": False,
            "body_policy": "bounded_plain_text" if include_body else "metadata_only",
        }

    def send_enabled():
        if not sender:
            return False
        try:
            if features and not any(s.get("live_enabled") for s in features.options().get("senders", [])):
                return False  # gateway may be enabled while no identity is authorized
            return mail.status().get("external_delivery_enabled") is True
        except Exception:
            return False

    def preparation(draft_id):
        with store.connect() as db:
            row = db.execute("SELECT payload FROM preparations WHERE draft_id=?", (draft_id,)).fetchone()
        return (row[0], json.loads(row[0])) if row else (None, None)

    def set_preparation(draft_id, expected_raw, record):
        # Compare-and-swap so two concurrent clicks cannot both send.
        with store.connect() as db:
            return db.execute("UPDATE preparations SET payload=? WHERE draft_id=? AND payload=?", (json.dumps(record), draft_id, expected_raw)).rowcount == 1

    def send_draft(data):
        if not isinstance(data, dict) or set(data) != {"id", "confirm"} or data["confirm"] is not True:
            raise ValueError("Explicit confirmation required")
        draft = store.get(data["id"])
        raw, prepared = preparation(draft["id"])
        # DraftStore.save deletes the preparation on every edit, so this is the reviewed version.
        if not prepared or prepared.get("state") != "prepared_not_sent":
            raise ValueError("Prepare the current version before sending")
        sending = {**prepared, "state": "sending"}
        if not set_preparation(draft["id"], raw, sending):
            raise ValueError("Draft is already being sent")
        try:
            outcome = sender.send(draft["payload"])
        except MailSendError as exc:
            # An unknown outcome stays blocked so a retry cannot duplicate the message.
            state = "send_outcome_unknown" if exc.code == "outcome_unknown" else "prepared_not_sent"
            set_preparation(draft["id"], json.dumps(sending), {**prepared, "state": state, "last_error": exc.code})
            raise
        delivery = outcome.get("delivery") or {}
        record = {**prepared, "state": "sent", "sent_at": datetime.now(timezone.utc).isoformat(), "message_id": delivery.get("message_id"), "recipient_count": delivery.get("recipient_count")}
        set_preparation(draft["id"], json.dumps(sending), record)
        return {"sent": True, "from_address": prepared.get("from_address"), "subject": prepared.get("subject"), "delivery": {k: delivery.get(k) for k in ("message_id", "recipient_count", "submitted_at", "provider")}}

    def review_record(message_id):
        if not security or not features or not features.source_path:
            raise ValueError('Security review unavailable')
        # Human review is isolated from signed mail/AVA read routes. No active content.
        from server.mail_correspondence_store import MailCorrespondenceStore
        canonical=MailCorrespondenceStore._message_id(message_id)
        with sqlite3.connect('file:'+str(features.source_path)+'?mode=ro',uri=True) as db:
            db.row_factory=sqlite3.Row
            row=db.execute("SELECT * FROM correspondence WHERE message_id=? AND source_authoritative=1 AND source_scope IN ('local_native','production_native')",(canonical,)).fetchone()
        if not row: raise ValueError('Message unavailable')
        return MailCorrespondenceStore._projection(row)

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
            if valid and session_check:
                valid = session_check(self.headers)
            if mutation:
                valid = valid and self.headers.get("Origin") == "https://edge1.ww.cx" and self.headers.get("X-Mail-Room-Request") == "1" and self.headers.get("Content-Type", "").split(";")[0] == "application/json"
            if not valid:
                self.reply(403, {"error": "Access denied"})
            return valid

        def do_GET(self):
            parsed = urlsplit(self.path)
            if parsed.path == PREFIX + "ava/messages":
                valid = bool(ava_read_key) and hmac.compare_digest(
                    self.headers.get("X-Ava-Mail-Read-Key", ""), str(ava_read_key)
                )
                if not valid:
                    self.reply(403, {"error": "Access denied"}); return
                try:
                    self.reply(200, ava_messages(parse_qs(parsed.query)))
                except (ValueError, RuntimeError, KeyError):
                    self.reply(422, {"error": "Mail Room read request rejected"})
                return
            if not self.authorized():
                return
            if not parsed.path.startswith(PREFIX):
                self.reply(404, {"error": "Not found"}); return
            route = parsed.path[len(PREFIX):]
            try:
                if route == "readiness":
                    data=json.loads(Path('/var/lib/wwcx-mail-room-reports/readiness.json').read_text())
                    data['access_policy']=ACCESS_POLICY
                elif route == "reports":
                    directory = Path("/var/lib/wwcx-mail-room-reports")
                    dates = sorted((p.stem for p in directory.glob("????-??-??.json")), reverse=True)[:31]
                    data = {"dates": dates, "timezone": "America/Regina"}
                elif route.startswith("report/"):
                    from datetime import date
                    requested = route[7:]
                    if date.fromisoformat(requested).isoformat() != requested: raise ValueError("Invalid report date")
                    data = json.loads((Path("/var/lib/wwcx-mail-room-reports") / (requested + ".json")).read_text())
                elif route == "status":
                    outlook_status = None
                    outlook_status_path = Path('/var/lib/wwcx-mail-room/outlook-graph/status.json')
                    if outlook_status_path.is_file() and not outlook_status_path.is_symlink():
                        try:
                            candidate = json.loads(outlook_status_path.read_text())
                            if isinstance(candidate, dict) and candidate.get('contract') == 'wwcx.outlook-graph-sync-status.v1':
                                outlook_status = candidate
                        except (OSError, ValueError):
                            outlook_status = {'error': {'type': 'StatusUnavailable', 'message': 'Outlook sync status is unreadable'}}
                    data = {"correspondence": mail.correspondence_status(), "provider_connected": os.getenv("WWCX_MAIL_PROVIDER_CONNECTED") == "true", "send_enabled": send_enabled(), "security_gate_enabled":security_required(), "updates":update_health(), "outlook_sync": outlook_status}
                elif route.startswith('security/') and security:
                    message_id=unquote(route[9:]); review_record(message_id)
                    data=security.get(message_id)
                elif route == 'filter-settings' and security:
                    data=security.settings()
                elif route == "senders" and features:
                    data = features.options()
                elif route == "activity" and features:
                    data = features.activity()
                elif route.startswith("attachments/") and features:
                    message_id = unquote(route[12:])
                    mail.correspondence_message(message_id=message_id)
                    with store.connect() as db:
                        try:
                            row = db.execute("SELECT payload FROM attachment_checks WHERE message_hash=?", (hashlib.sha256(message_id.encode()).hexdigest(),)).fetchone()
                        except sqlite3.OperationalError:
                            row = None
                    data = json.loads(row[0]) if row else {"attachments": [], "indexed": False, "downloads_enabled": False, "scanner_ready": False}
                elif route == "messages" and features:
                    data = features.messages(parse_qs(parsed.query))
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
                elif self.path == PREFIX + 'security-action' and security:
                    if not isinstance(data,dict) or set(data)-{'message_id','action','interacted','reviewed'} or not {'message_id','action'} <= set(data): raise ValueError('Invalid security action')
                    if data['action']=='release' and data.get('reviewed') is not True: raise ValueError('Reviewed release required')
                    review_record(data['message_id'])
                    result=security.action(data['message_id'],data['action'],data.get('interacted',False))
                elif self.path == PREFIX + 'filter-settings' and security:
                    result=security.settings(data)
                elif self.path == PREFIX + 'review' and security:
                    if not isinstance(data,dict) or set(data)!={'message_id','acknowledged'} or data['acknowledged'] is not True: raise ValueError('Review acknowledgement required')
                    result={'message':review_record(data['message_id']),'security':security.get(data['message_id']),'content_is_untrusted':True,'ai_available':False,'downloads_enabled':False}
                elif self.path == PREFIX + "prepare":
                    if not isinstance(data, dict) or set(data) != {"id"}:
                        raise ValueError("Draft ID required")
                    draft = store.get(data["id"])
                    result = mail.prepare_draft(draft["payload"])
                    if features:
                        features.record_preparation(draft["id"], result, datetime.now(timezone.utc).isoformat())
                elif self.path == PREFIX + "send" and sender:
                    result = send_draft(data)
                elif self.path == PREFIX + "flags" and features:
                    if not isinstance(data, dict): raise ValueError("Invalid flags")
                    if set(data) == {'message_id', 'deleted'}:
                        # Organizing held mail needs existence, not permission to read its body.
                        from server.mail_correspondence_store import MailCorrespondenceStore
                        canonical=MailCorrespondenceStore._message_id(data['message_id'])
                        if not features.source_path: raise ValueError('Mail source unavailable')
                        with sqlite3.connect('file:'+str(features.source_path)+'?mode=ro',uri=True) as db:
                            exists=db.execute("SELECT 1 FROM correspondence WHERE message_id=? AND source_authoritative=1 AND source_scope IN ('local_native','production_native')",(canonical,)).fetchone()
                        if not exists: raise ValueError('Message unavailable')
                    else:
                        mail.correspondence_message(message_id=data.get("message_id", ""))
                    result = features.flags(data)
                elif self.path == PREFIX + "signature" and features:
                    result = features.signature(data)
                elif self.path == PREFIX + "assist" and assistant:
                    if not isinstance(data, dict) or set(data) != {"operation", "thread_id"}: raise ValueError("Invalid assistance request")
                    thread = mail.correspondence_thread(thread_id=data["thread_id"])["thread"]
                    result = assistant.assist(data["operation"], thread)
                else:
                    self.reply(404, {"error": "Not found"}); return
                self.reply(200, result)
            except MailSendError as exc:
                self.reply(409 if exc.code == "outcome_unknown" else 422, {"error": "Not sent: " + str(exc), "code": exc.code})
            except (ValueError, TypeError, KeyError) as exc:
                if self.path == PREFIX + "send":
                    self.reply(400, {"error": str(exc) if isinstance(exc, ValueError) else "Draft not found"}); return
                self.reply(400, {"error": "Security action unavailable or release blocked. Complete checks and no hard security finding are required." if self.path in {PREFIX+'security-action',PREFIX+'review'} else "Invalid draft request"})
            except Exception:
                if self.path == PREFIX + "flags":
                    self.reply(503, {"error": "Message organization could not be saved. Please retry."}); return
                self.reply(503 if self.path == PREFIX + "assist" else 422, {"error": "AVA is unavailable; no draft was changed." if self.path == PREFIX + "assist" else "Preparation could not complete. Check required signature, sender and recipient fields. Draft remains saved; nothing sent."})

    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8117)
    args = parser.parse_args()
    os.umask(0o077)
    mail = BigBirdMailTools(MailToolConfig.from_environment())
    store = DraftStore(args.database)
    identities = json.loads(Path("/etc/wwcx/outbound-mail/identities.json").read_text())
    features = MailRoomFeatures(store, "/var/lib/wwcx-mail-room/correspondence.sqlite3", identities)
    handler = make_handler(
        mail, store, os.environ["WWCX_MAIL_ROOM_PROXY_KEY"], features, AvaMailAssistant(),
        SecurityStore() if security_required() else None, session_check=admin_session,
        sender=MailRoomSendClient.from_environment(), ava_read_key=os.environ.get("WWCX_AVA_MAIL_READ_KEY"),
    )
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    server.timeout = 10
    server.serve_forever()


if __name__ == "__main__":
    main()
