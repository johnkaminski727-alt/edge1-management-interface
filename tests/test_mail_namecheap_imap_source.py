from __future__ import annotations

import pathlib
import sys

import pytest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVER = ROOT / "server"
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))

from mail_namecheap_imap_source import (
    NAMECHEAP_IMAP_HOST,
    NAMECHEAP_IMAP_PORT,
    NamecheapIMAPConfig,
    NamecheapIMAPSourceError,
    ingest_namecheap_private_email,
    open_namecheap_store,
)


ROOT_MESSAGE = b"\r\n".join(
    [
        b"From: sender@example.test",
        b"To: john@ww.cx",
        b"Date: Thu, 20 Aug 2026 20:00:00 +0000",
        b"Message-ID: <provider-root@example.test>",
        b"Subject: Provider correspondence root",
        b"Content-Type: text/plain; charset=utf-8",
        b"",
        b"Provider-native body remains untrusted data.",
        b"",
    ]
)

REPLY_MESSAGE = b"\r\n".join(
    [
        b"From: responder@example.test",
        b"To: records@ww.cx",
        b"Date: Thu, 20 Aug 2026 20:05:00 +0000",
        b"Message-ID: <provider-reply@example.test>",
        b"In-Reply-To: <provider-root@example.test>",
        b"References: <provider-root@example.test>",
        b"Subject: Re: Provider correspondence root",
        b"Content-Type: text/plain; charset=utf-8",
        b"",
        b"Provider-native reply.",
        b"",
    ]
)

HTML_ONLY_MESSAGE = b"\r\n".join(
    [
        b"From: html@example.test",
        b"To: john@ww.cx",
        b"Date: Thu, 20 Aug 2026 20:03:00 +0000",
        b"Message-ID: <provider-html@example.test>",
        b"Subject: HTML only",
        b"Content-Type: text/html; charset=utf-8",
        b"",
        b"<p>Do not persist unsafe HTML as correspondence.</p>",
        b"",
    ]
)

MISSING_ID_MESSAGE = b"\r\n".join(
    [
        b"From: no-id@example.test",
        b"To: john@ww.cx",
        b"Date: Thu, 20 Aug 2026 20:04:00 +0000",
        b"Subject: Missing ID",
        b"Content-Type: text/plain; charset=utf-8",
        b"",
        b"This message has no Message-ID.",
        b"",
    ]
)


class FakeIMAP:
    def __init__(self, messages: dict[bytes, bytes], *, login_ok: bool = True) -> None:
        self.messages = messages
        self.login_ok = login_ok
        self.calls: list[tuple] = []
        self.readonly = None

    def login(self, user: str, password: str):
        self.calls.append(("login", user, password))
        if not self.login_ok:
            return "NO", [b"bad credentials"]
        return "OK", [b"logged in"]

    def select(self, mailbox: str = "INBOX", readonly: bool = False):
        self.calls.append(("select", mailbox, readonly))
        self.readonly = readonly
        return "OK", [str(len(self.messages)).encode("ascii")]

    def response(self, code: str):
        self.calls.append(("response", code))
        return "UIDVALIDITY", [b"4242"]

    def uid(self, command: str, *args):
        self.calls.append(("uid", command, *args))
        if command == "SEARCH":
            return "OK", [b" ".join(self.messages)]
        if command == "FETCH":
            uid = args[0]
            payload = self.messages[uid]
            return "OK", [(b"1 (BODY[] {%d}" % len(payload), payload), b")"]
        raise AssertionError(f"unexpected IMAP UID command: {command}")

    def logout(self):
        self.calls.append(("logout",))
        return "BYE", [b"logout"]


def _assert_read_only_calls(session: FakeIMAP) -> None:
    assert session.readonly is True
    uid_calls = [call for call in session.calls if call[0] == "uid"]
    commands = [call[1] for call in uid_calls]
    assert commands
    assert set(commands) <= {"SEARCH", "FETCH"}
    fetch_calls = [call for call in uid_calls if call[1] == "FETCH"]
    assert fetch_calls
    assert all(call[-1] == "(BODY.PEEK[])" for call in fetch_calls)
    forbidden = {"STORE", "MOVE", "COPY", "DELETE", "EXPUNGE", "APPEND"}
    assert forbidden.isdisjoint(commands)


def test_namecheap_imap_ingests_provider_native_without_mailbox_mutation(tmp_path):
    db_path = tmp_path / "mail-room" / "correspondence.sqlite3"
    store = open_namecheap_store(db_path)
    session = FakeIMAP({b"101": ROOT_MESSAGE, b"102": REPLY_MESSAGE})
    secret = "not-a-real-secret"

    result = ingest_namecheap_private_email(
        NamecheapIMAPConfig(username="blank@ww.cx", max_messages=10),
        store,
        password_provider=lambda: secret,
        session_factory=lambda: session,
    )

    assert result["endpoint"] == NAMECHEAP_IMAP_HOST
    assert result["port"] == NAMECHEAP_IMAP_PORT
    assert result["uidvalidity"] == "4242"
    assert result["ingested_count"] == 2
    assert result["skipped_count"] == 0
    assert result["failed_count"] == 0
    assert result["complete"] is True
    assert result["mailbox_read_only"] is True
    assert result["send_authorized"] is False
    assert result["mutation_authorized"] is False
    assert result["credential_returned"] is False
    assert secret not in repr(result)

    first = store.read_message("<provider-root@example.test>")
    second = store.read_message("<provider-reply@example.test>")
    assert first["provenance"] == {
        "source": "namecheap-private-email-imap",
        "scope": "production_native",
        "authoritative": True,
    }
    assert first["content_is_untrusted"] is True
    assert first["send_authorized"] is False
    assert first["mutation_authorized"] is False
    assert first["recipients"] == ["john@ww.cx"]
    assert second["thread_id"] == first["thread_id"]
    _assert_read_only_calls(session)


def test_namecheap_imap_repeat_is_idempotent_by_message_id(tmp_path):
    store = open_namecheap_store(tmp_path / "mail-room" / "correspondence.sqlite3")
    first_session = FakeIMAP({b"101": ROOT_MESSAGE})
    second_session = FakeIMAP({b"101": ROOT_MESSAGE})
    config = NamecheapIMAPConfig(username="blank@ww.cx")

    first = ingest_namecheap_private_email(
        config,
        store,
        password_provider=lambda: "secret-one",
        session_factory=lambda: first_session,
    )
    second = ingest_namecheap_private_email(
        config,
        store,
        password_provider=lambda: "secret-two",
        session_factory=lambda: second_session,
    )

    assert first["ingested_count"] == 1
    assert second["ingested_count"] == 0
    assert second["skipped_count"] == 1
    assert second["failed_count"] == 0
    assert second["skipped"][0]["reason"] == "already_ingested"
    assert store.status()["record_count"] == 1
    _assert_read_only_calls(second_session)


def test_namecheap_imap_bounded_tail_fetch_sorts_numeric_uids(tmp_path):
    store = open_namecheap_store(tmp_path / "mail-room" / "correspondence.sqlite3")
    messages = {
        b"10": REPLY_MESSAGE,
        b"2": ROOT_MESSAGE,
        b"1": ROOT_MESSAGE.replace(b"provider-root", b"provider-old"),
    }
    session = FakeIMAP(messages)

    result = ingest_namecheap_private_email(
        NamecheapIMAPConfig(username="blank@ww.cx", max_messages=2),
        store,
        password_provider=lambda: "secret",
        session_factory=lambda: session,
    )

    assert result["selected_count"] == 2
    fetched = [call[2] for call in session.calls if call[:2] == ("uid", "FETCH")]
    assert fetched == [b"2", b"10"]
    _assert_read_only_calls(session)


def test_namecheap_imap_isolates_rejected_messages_and_continues(tmp_path):
    store = open_namecheap_store(tmp_path / "mail-room" / "correspondence.sqlite3")
    session = FakeIMAP(
        {
            b"101": ROOT_MESSAGE,
            b"102": HTML_ONLY_MESSAGE,
            b"103": MISSING_ID_MESSAGE,
            b"104": REPLY_MESSAGE,
        }
    )

    result = ingest_namecheap_private_email(
        NamecheapIMAPConfig(username="blank@ww.cx", max_messages=10),
        store,
        password_provider=lambda: "secret",
        session_factory=lambda: session,
    )

    assert result["ingested_count"] == 2
    assert result["failed_count"] == 2
    assert result["complete"] is False
    assert result["failed"] == [
        {
            "uid": "102",
            "message_id": "<provider-html@example.test>",
            "reason": "normalization_rejected",
        },
        {"uid": "103", "reason": "invalid_message_id"},
    ]
    assert store.status()["record_count"] == 2
    assert (
        store.read_message("<provider-root@example.test>")["provenance"]["scope"]
        == "production_native"
    )
    _assert_read_only_calls(session)


def test_namecheap_imap_fails_closed_on_bad_configuration(tmp_path):
    store = open_namecheap_store(tmp_path / "mail-room" / "correspondence.sqlite3")

    with pytest.raises(NamecheapIMAPSourceError):
        ingest_namecheap_private_email(
            NamecheapIMAPConfig(username="not-an-address"),
            store,
            password_provider=lambda: "secret",
            session_factory=lambda: FakeIMAP({}),
        )

    with pytest.raises(NamecheapIMAPSourceError):
        ingest_namecheap_private_email(
            NamecheapIMAPConfig(username="blank@ww.cx", mailbox="Archive"),
            store,
            password_provider=lambda: "secret",
            session_factory=lambda: FakeIMAP({}),
        )

    with pytest.raises(NamecheapIMAPSourceError):
        ingest_namecheap_private_email(
            NamecheapIMAPConfig(username="blank@ww.cx", max_messages=101),
            store,
            password_provider=lambda: "secret",
            session_factory=lambda: FakeIMAP({}),
        )

    with pytest.raises(NamecheapIMAPSourceError):
        ingest_namecheap_private_email(
            NamecheapIMAPConfig(username="blank@ww.cx"),
            store,
            password_provider=lambda: "",
            session_factory=lambda: FakeIMAP({}),
        )


def test_namecheap_imap_login_failure_does_not_fetch(tmp_path):
    store = open_namecheap_store(tmp_path / "mail-room" / "correspondence.sqlite3")
    session = FakeIMAP({b"101": ROOT_MESSAGE}, login_ok=False)

    with pytest.raises(NamecheapIMAPSourceError):
        ingest_namecheap_private_email(
            NamecheapIMAPConfig(username="blank@ww.cx"),
            store,
            password_provider=lambda: "secret",
            session_factory=lambda: session,
        )

    assert not any(call[0] == "uid" for call in session.calls)
