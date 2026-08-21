from __future__ import annotations

import pathlib
import sys
from datetime import datetime, timedelta, timezone

import pytest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVER = ROOT / "server"
TOOLS = ROOT / "tools" / "messaging"
for path in (SERVER, TOOLS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from mail_namecheap_imap_source import open_namecheap_store
from namecheap_imap_ingestion_acceptance import (
    AUTH_CONTRACT,
    NAMECHEAP_IMAP_HOST,
    NAMECHEAP_IMAP_PORT,
    NamecheapIMAPIngestionAcceptanceError,
    _sha256,
    audit_result,
    run_acceptance,
)


MESSAGE = b"\r\n".join(
    [
        b"From: sender@example.test",
        b"To: visible-role@ww.cx",
        b"Delivered-To: blank@ww.cx",
        b"X-Original-To: original-local-part@ww.cx",
        b"Date: Fri, 21 Aug 2026 02:30:00 +0000",
        b"Message-ID: <live-acceptance@example.test>",
        b"Subject: Live ingestion acceptance fixture",
        b"Content-Type: text/plain; charset=utf-8",
        b"",
        b"Full message content is persisted only in the private test store.",
        b"",
    ]
)


class FakeIMAP:
    def __init__(self, message: bytes) -> None:
        self.message = message
        self.readonly = None
        self.calls: list[tuple] = []

    def login(self, user: str, password: str):
        self.calls.append(("login", user, password))
        return "OK", [b"logged in"]

    def select(self, mailbox: str = "INBOX", readonly: bool = False):
        self.calls.append(("select", mailbox, readonly))
        self.readonly = readonly
        return "OK", [b"1"]

    def response(self, code: str):
        return "UIDVALIDITY", [b"5150"]

    def uid(self, command: str, *args):
        self.calls.append(("uid", command, *args))
        if command == "SEARCH":
            return "OK", [b"77"]
        if command == "FETCH":
            return "OK", [(b"1 (BODY[] {1}", self.message), b")"]
        raise AssertionError(command)

    def logout(self):
        self.calls.append(("logout",))
        return "BYE", [b"logout"]


def _authorization(store_path: pathlib.Path, *, max_messages: int = 1, polling: bool = False):
    return {
        "contract": AUTH_CONTRACT,
        "provider_ingestion_authorized": True,
        "expected_host_sha256": _sha256(NAMECHEAP_IMAP_HOST),
        "expected_port": NAMECHEAP_IMAP_PORT,
        "expected_username_sha256": _sha256("blank@ww.cx"),
        "expected_store_path_sha256": _sha256(str(store_path)),
        "mailbox": "INBOX",
        "max_messages": max_messages,
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(),
        "full_message_fetch_authorized": True,
        "production_native_store_write_authorized": True,
        "mailbox_mutation_authorized": False,
        "mail_send_authorized": False,
        "provider_mutation_authorized": False,
        "persistent_polling_authorized": polling,
    }


def test_live_acceptance_writes_exactly_one_sanitized_provider_record(tmp_path):
    store_path = tmp_path / "mail-room" / "correspondence.sqlite3"
    open_namecheap_store(store_path)
    settings = {"username": "blank@ww.cx", "password": "test-secret"}
    session = FakeIMAP(MESSAGE)

    result = run_acceptance(
        settings,
        _authorization(store_path),
        store_path=store_path,
        backup_root=tmp_path / "backups",
        session_factory=lambda: session,
    )

    assert result["selected_count"] == 1
    assert result["ingested_count"] == 1
    assert result["record_count_before"] == 0
    assert result["record_count_after"] == 1
    assert result["full_message_fetched"] is True
    assert result["production_native_store_write"] is True
    assert result["mailbox_read_only"] is True
    assert result["content_output"] is False
    assert result["credentials_output"] is False
    assert result["message"]["provenance"] == {
        "source": "namecheap-private-email-imap",
        "scope": "production_native",
        "authoritative": True,
    }
    assert result["message"]["content_is_untrusted"] is True
    assert "live-acceptance@example.test" not in repr(result)
    assert "Full message content" not in repr(result)
    assert "original-local-part@ww.cx" not in repr(result)
    assert "test-secret" not in repr(result)
    assert settings["password"] == ""
    assert session.readonly is True
    assert all(call[1] in {"SEARCH", "FETCH"} for call in session.calls if call[0] == "uid")

    stored = open_namecheap_store(store_path).read_message("<live-acceptance@example.test>")
    assert stored["recipients"] == ["original-local-part@ww.cx"]
    assert stored["body_text"].startswith("Full message content")


def test_live_acceptance_rejects_message_without_provider_recipient_evidence(tmp_path):
    store_path = tmp_path / "mail-room" / "correspondence.sqlite3"
    store = open_namecheap_store(store_path)
    missing = MESSAGE.replace(b"Delivered-To: blank@ww.cx\r\n", b"").replace(
        b"X-Original-To: original-local-part@ww.cx\r\n", b""
    )

    with pytest.raises(NamecheapIMAPIngestionAcceptanceError):
        run_acceptance(
            {"username": "blank@ww.cx", "password": "test-secret"},
            _authorization(store_path),
            store_path=store_path,
            backup_root=tmp_path / "backups",
            session_factory=lambda: FakeIMAP(missing),
        )

    assert store.status()["record_count"] == 0


def test_authorization_rejects_broader_fetch_or_persistent_polling(tmp_path):
    store_path = tmp_path / "mail-room" / "correspondence.sqlite3"

    with pytest.raises(NamecheapIMAPIngestionAcceptanceError):
        audit_result(_authorization(store_path, max_messages=2), store_path=store_path)

    with pytest.raises(NamecheapIMAPIngestionAcceptanceError):
        audit_result(_authorization(store_path, polling=True), store_path=store_path)
