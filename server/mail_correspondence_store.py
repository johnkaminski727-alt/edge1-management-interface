#!/usr/bin/env python3
"""Private persisted Mail Room correspondence store.

The store is transport-neutral and performs no network activity. Writers must identify
an upstream source, authority decision, and scope. Those provenance fields are persisted
per record and can never be upgraded by a later reader configuration.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote


MESSAGE_ID_RE = re.compile(r"^<[^<>\r\n\s]+@[^<>\r\n\s]+>$")
CONTROL_ID_RE = re.compile(r"^[A-Z0-9][A-Z0-9._:-]{5,127}$")
MAX_BODY_CHARS = 100_000
MAX_SUBJECT_CHARS = 998
MAX_ADDRESS_CHARS = 320
MAX_PROVIDER_ID_CHARS = 512
MAX_THREAD_RESULTS = 100
SOURCE_SCOPES = {"synthetic", "local_native", "production_native", "legacy_unscoped"}
READABLE_AUTHORITATIVE_SCOPES = {"local_native", "production_native"}


class CorrespondenceStoreError(RuntimeError):
    pass


class MailCorrespondenceStore:
    """Private SQLite correspondence store with immutable per-record provenance."""

    def __init__(
        self,
        path: str | Path,
        *,
        source: str,
        source_authoritative: bool = False,
        source_scope: str = "synthetic",
        read_only: bool = False,
    ) -> None:
        self.path = Path(path).absolute()
        self.source = str(source).strip()
        self.source_scope = str(source_scope).strip()
        self.source_authoritative = bool(source_authoritative)
        self.read_only = bool(read_only)
        if not self.source or len(self.source) > 128:
            raise CorrespondenceStoreError("source is required and must be bounded")
        if self.source_scope not in SOURCE_SCOPES:
            raise CorrespondenceStoreError("source_scope is invalid")
        if self.source_authoritative and self.source_scope not in READABLE_AUTHORITATIVE_SCOPES:
            raise CorrespondenceStoreError(
                "authoritative correspondence must use local_native or production_native scope"
            )
        if self.path.exists() and self.path.is_symlink():
            raise CorrespondenceStoreError("correspondence database may not be a symlink")

        if self.read_only:
            if not self.path.is_file():
                raise CorrespondenceStoreError("correspondence database is unavailable")
            if self.path.parent.is_symlink():
                raise CorrespondenceStoreError("correspondence directory may not be a symlink")
            if os.stat(self.path).st_mode & 0o077:
                raise CorrespondenceStoreError("correspondence database permissions are too broad")
            self._verify_schema()
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            if self.path.parent.is_symlink():
                raise CorrespondenceStoreError("correspondence directory may not be a symlink")
            os.chmod(self.path.parent, 0o700)
            self._initialize()

    def _connect(self) -> sqlite3.Connection:
        if self.read_only:
            encoded = quote(str(self.path), safe="/")
            connection = sqlite3.connect(f"file:{encoded}?mode=ro", uri=True)
        else:
            connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _required_columns() -> set[str]:
        return {
            "message_id",
            "provider_message_id",
            "provider_thread_id",
            "thread_id",
            "direction",
            "sender",
            "recipients_json",
            "subject",
            "body_text",
            "in_reply_to",
            "references_json",
            "occurred_at",
            "source",
            "source_authoritative",
            "source_scope",
        }

    def _columns(self, db: sqlite3.Connection) -> set[str]:
        return {str(row["name"]) for row in db.execute("PRAGMA table_info(correspondence)")}

    def _verify_schema(self) -> None:
        with self._connect() as db:
            columns = self._columns(db)
        missing = self._required_columns() - columns
        if missing:
            raise CorrespondenceStoreError(
                "correspondence database requires a writable schema migration: "
                + ",".join(sorted(missing))
            )

    def _initialize(self) -> None:
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS correspondence (
                    message_id TEXT PRIMARY KEY,
                    provider_message_id TEXT,
                    provider_thread_id TEXT,
                    thread_id TEXT NOT NULL,
                    direction TEXT NOT NULL CHECK(direction IN ('inbound','outbound')),
                    sender TEXT NOT NULL,
                    recipients_json TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    body_text TEXT NOT NULL,
                    in_reply_to TEXT,
                    references_json TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    source TEXT NOT NULL,
                    source_authoritative INTEGER NOT NULL CHECK(source_authoritative IN (0,1)),
                    source_scope TEXT NOT NULL DEFAULT 'legacy_unscoped'
                );
                """
            )
            columns = self._columns(db)
            if "source_authoritative" not in columns:
                db.execute(
                    "ALTER TABLE correspondence ADD COLUMN source_authoritative "
                    "INTEGER NOT NULL DEFAULT 0"
                )
            columns = self._columns(db)
            if "source_scope" not in columns:
                db.execute(
                    "ALTER TABLE correspondence ADD COLUMN source_scope "
                    "TEXT NOT NULL DEFAULT 'legacy_unscoped'"
                )
            db.execute(
                "CREATE INDEX IF NOT EXISTS correspondence_thread_idx "
                "ON correspondence(thread_id, occurred_at, message_id)"
            )
        os.chmod(self.path, 0o600)
        self._verify_schema()

    @staticmethod
    def _message_id(value: Any, label: str = "message_id") -> str:
        text = str(value or "").strip()
        if len(text) > 998 or not MESSAGE_ID_RE.fullmatch(text):
            raise CorrespondenceStoreError(f"{label} must be a canonical Message-ID")
        return text

    @staticmethod
    def _control_id(value: Any, label: str) -> str:
        text = str(value or "").strip()
        if not CONTROL_ID_RE.fullmatch(text):
            raise CorrespondenceStoreError(f"{label} is invalid")
        return text

    @staticmethod
    def _text(value: Any, label: str, maximum: int) -> str:
        text = str(value or "")
        if len(text) > maximum or "\x00" in text:
            raise CorrespondenceStoreError(f"{label} exceeds safe bounds")
        return text

    @classmethod
    def _address(cls, value: Any, label: str) -> str:
        text = cls._text(value, label, MAX_ADDRESS_CHARS).strip()
        if "\r" in text or "\n" in text or text.count("@") != 1:
            raise CorrespondenceStoreError(f"{label} is invalid")
        local, domain = text.rsplit("@", 1)
        if not local or not domain:
            raise CorrespondenceStoreError(f"{label} is invalid")
        return text

    @classmethod
    def _addresses(cls, value: Any, label: str, maximum: int) -> list[str]:
        if not isinstance(value, list) or not value or len(value) > maximum:
            raise CorrespondenceStoreError(f"{label} exceeds safe bounds")
        return [cls._address(item, f"{label} item") for item in value]

    @staticmethod
    def _occurred_at(value: Any) -> str:
        text = str(value or "").strip()
        if not text or len(text) > 64:
            raise CorrespondenceStoreError("occurred_at is invalid")
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError as exc:
            raise CorrespondenceStoreError("occurred_at must be ISO-8601") from exc
        if parsed.tzinfo is None:
            raise CorrespondenceStoreError("occurred_at must include a timezone")
        return text

    def ingest(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.read_only:
            raise CorrespondenceStoreError("read-only correspondence store cannot ingest")
        if not isinstance(payload, dict):
            raise CorrespondenceStoreError("message payload must be an object")
        message_id = self._message_id(payload.get("message_id"))
        thread_id = self._control_id(payload.get("thread_id"), "thread_id")
        direction = str(payload.get("direction", "")).strip()
        if direction not in {"inbound", "outbound"}:
            raise CorrespondenceStoreError("direction is invalid")
        sender = self._address(payload.get("sender"), "sender")
        recipients = self._addresses(payload.get("recipients"), "recipients", 100)
        subject = self._text(payload.get("subject"), "subject", MAX_SUBJECT_CHARS)
        body_text = self._text(payload.get("body_text"), "body_text", MAX_BODY_CHARS)
        references_raw = payload.get("references", [])
        if not isinstance(references_raw, list) or len(references_raw) > 100:
            raise CorrespondenceStoreError("references exceeds safe bounds")
        references = [self._message_id(item, "reference") for item in references_raw]
        in_reply_to = payload.get("in_reply_to")
        if in_reply_to is not None:
            in_reply_to = self._message_id(in_reply_to, "in_reply_to")
            if in_reply_to not in references:
                references.append(in_reply_to)
        occurred_at = self._occurred_at(payload.get("occurred_at"))
        provider_message_id = payload.get("provider_message_id")
        provider_thread_id = payload.get("provider_thread_id")
        provider_message_id = (
            None
            if provider_message_id is None
            else self._text(provider_message_id, "provider_message_id", MAX_PROVIDER_ID_CHARS)
        )
        provider_thread_id = (
            None
            if provider_thread_id is None
            else self._text(provider_thread_id, "provider_thread_id", MAX_PROVIDER_ID_CHARS)
        )

        try:
            with self._connect() as db:
                db.execute(
                    """INSERT INTO correspondence(
                    message_id, provider_message_id, provider_thread_id, thread_id, direction,
                    sender, recipients_json, subject, body_text, in_reply_to, references_json,
                    occurred_at, source, source_authoritative, source_scope)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        message_id,
                        provider_message_id,
                        provider_thread_id,
                        thread_id,
                        direction,
                        sender,
                        json.dumps(recipients, separators=(",", ":")),
                        subject,
                        body_text,
                        in_reply_to,
                        json.dumps(references, separators=(",", ":")),
                        occurred_at,
                        self.source,
                        1 if self.source_authoritative else 0,
                        self.source_scope,
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise CorrespondenceStoreError("message_id already exists or record is invalid") from exc
        os.chmod(self.path, 0o600)
        return self.read_message(message_id)

    def read_message(self, message_id: str) -> dict[str, Any]:
        canonical = self._message_id(message_id)
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM correspondence WHERE message_id = ?", (canonical,)
            ).fetchone()
        if row is None:
            raise CorrespondenceStoreError("message not found")
        return self._projection(row)

    def read_thread(self, thread_id: str, *, limit: int = 50) -> dict[str, Any]:
        canonical_thread = self._control_id(thread_id, "thread_id")
        if not isinstance(limit, int) or not 1 <= limit <= MAX_THREAD_RESULTS:
            raise CorrespondenceStoreError("thread result limit is invalid")
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM correspondence WHERE thread_id = ? "
                "ORDER BY occurred_at, message_id LIMIT ?",
                (canonical_thread, limit),
            ).fetchall()
        if not rows:
            raise CorrespondenceStoreError("thread not found")
        return {
            "contract": "wwcx.mail-correspondence-thread.v1",
            "thread_id": canonical_thread,
            "messages": [self._projection(row) for row in rows],
            "count": len(rows),
            "content_is_untrusted": True,
            "mutation_authorized": False,
            "send_authorized": False,
        }

    def status(self) -> dict[str, Any]:
        with self._connect() as db:
            count = int(db.execute("SELECT COUNT(*) FROM correspondence").fetchone()[0])
            rows = db.execute(
                "SELECT source, source_scope, source_authoritative, COUNT(*) AS record_count "
                "FROM correspondence GROUP BY source, source_scope, source_authoritative "
                "ORDER BY source, source_scope, source_authoritative"
            ).fetchall()
        return {
            "contract": "wwcx.mail-correspondence-store-status.v1",
            "record_count": count,
            "sources": [
                {
                    "source": row["source"],
                    "scope": row["source_scope"],
                    "authoritative": bool(row["source_authoritative"]),
                    "record_count": int(row["record_count"]),
                }
                for row in rows
            ],
            "read_only": self.read_only,
            "mutation_authorized": False,
            "send_authorized": False,
        }

    @staticmethod
    def _projection(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "contract": "wwcx.mail-correspondence-message.v1",
            "message_id": row["message_id"],
            "provider_message_id": row["provider_message_id"],
            "provider_thread_id": row["provider_thread_id"],
            "thread_id": row["thread_id"],
            "direction": row["direction"],
            "sender": row["sender"],
            "recipients": json.loads(row["recipients_json"]),
            "subject": row["subject"],
            "body_text": row["body_text"],
            "in_reply_to": row["in_reply_to"],
            "references": json.loads(row["references_json"]),
            "occurred_at": row["occurred_at"],
            "provenance": {
                "source": row["source"],
                "scope": row["source_scope"],
                "authoritative": bool(row["source_authoritative"]),
            },
            "content_is_untrusted": True,
            "mutation_authorized": False,
            "send_authorized": False,
        }
