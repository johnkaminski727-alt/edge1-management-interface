#!/usr/bin/env python3
"""Read-only Namecheap Private Email source for WW.CX Mail Room correspondence.

This module provides a credential-injected IMAP bridge from an existing Namecheap
Private Email mailbox into the private WW.CX correspondence store. It is deliberately
not registered, scheduled, or activated by importing this module.

Security properties:
- hard-pinned Namecheap Private Email IMAP endpoint over verified TLS;
- full mailbox address is required as the IMAP username;
- credentials are supplied at call time and are never persisted or returned;
- mailbox is selected read-only;
- messages are fetched with BODY.PEEK[] so they are not marked Seen;
- no STORE, MOVE, COPY, DELETE, EXPUNGE, APPEND, or SMTP operation exists here;
- provider mail is persisted as authoritative ``production_native`` correspondence;
- Namecheap original-recipient evidence is required per message and takes precedence
  over visible To/Cc headers, preventing Catch-All/Bcc/forward misattribution;
- duplicate RFC Message-ID values are skipped idempotently rather than rewritten;
- malformed/unsupported messages fail closed individually without blocking safe peers.
"""

from __future__ import annotations

import imaplib
import re
import ssl
from dataclasses import dataclass
from email import policy
from email.parser import BytesParser
from email.utils import getaddresses
from pathlib import Path
from typing import Callable, Protocol, Sequence

from mail_correspondence_store import CorrespondenceStoreError, MailCorrespondenceStore
from mail_local_rfc822_source import LocalMailSourceError, normalize_rfc822


NAMECHEAP_IMAP_HOST = "mail.privateemail.com"
NAMECHEAP_IMAP_PORT = 993
NAMECHEAP_SOURCE = "namecheap-private-email-imap"
NAMECHEAP_SCOPE = "production_native"
MAX_FETCH_MESSAGES = 100
_MAILBOX_ADDRESS_RE = re.compile(r"^[^\s@]+@[^\s@]+$")
_UID_RE = re.compile(rb"^[1-9][0-9]*$")
_ORIGINAL_RECIPIENT_HEADERS = ("X-Original-To", "Delivered-To")


class NamecheapIMAPSourceError(RuntimeError):
    """Raised when the provider source cannot safely complete a read."""


class IMAPSession(Protocol):
    def login(self, user: str, password: str): ...
    def select(self, mailbox: str = "INBOX", readonly: bool = False): ...
    def uid(self, command: str, *args): ...
    def response(self, code: str): ...
    def logout(self): ...


@dataclass(frozen=True)
class NamecheapIMAPConfig:
    """Non-secret configuration for one Namecheap Private Email mailbox."""

    username: str
    mailbox: str = "INBOX"
    max_messages: int = 50

    def validate(self) -> None:
        if not _MAILBOX_ADDRESS_RE.fullmatch(self.username):
            raise NamecheapIMAPSourceError("IMAP username must be the full mailbox address")
        if self.mailbox != "INBOX":
            raise NamecheapIMAPSourceError("only the INBOX mailbox is supported")
        if not isinstance(self.max_messages, int) or not 1 <= self.max_messages <= MAX_FETCH_MESSAGES:
            raise NamecheapIMAPSourceError(
                f"max_messages must be between 1 and {MAX_FETCH_MESSAGES}"
            )


def open_namecheap_store(path: str | Path) -> MailCorrespondenceStore:
    """Open the private correspondence store with immutable provider provenance."""

    return MailCorrespondenceStore(
        path,
        source=NAMECHEAP_SOURCE,
        source_authoritative=True,
        source_scope=NAMECHEAP_SCOPE,
    )


def _default_session_factory() -> IMAPSession:
    context = ssl.create_default_context()
    return imaplib.IMAP4_SSL(
        NAMECHEAP_IMAP_HOST,
        NAMECHEAP_IMAP_PORT,
        ssl_context=context,
        timeout=20,
    )


def _ok(status: object, label: str) -> None:
    if str(status).upper() != "OK":
        raise NamecheapIMAPSourceError(f"IMAP {label} failed")


def _uidvalidity(session: IMAPSession) -> str | None:
    response = session.response("UIDVALIDITY")
    if not response or len(response) < 2:
        return None
    values = response[1]
    if not values:
        return None
    raw = values[0]
    if isinstance(raw, bytes):
        text = raw.decode("ascii", "strict").strip()
    else:
        text = str(raw).strip()
    return text if text.isdigit() else None


def _search_uids(session: IMAPSession) -> list[bytes]:
    status, data = session.uid("SEARCH", None, "ALL")
    _ok(status, "UID SEARCH")
    if not data:
        return []
    first = data[0]
    if not isinstance(first, bytes):
        raise NamecheapIMAPSourceError("IMAP UID SEARCH returned an invalid response")
    uids = first.split()
    if any(not _UID_RE.fullmatch(uid) for uid in uids):
        raise NamecheapIMAPSourceError("IMAP UID SEARCH returned an invalid UID")
    return sorted(uids, key=lambda value: int(value))


def _fetch_raw(session: IMAPSession, uid: bytes) -> bytes:
    status, data = session.uid("FETCH", uid, "(BODY.PEEK[])")
    _ok(status, "UID FETCH")
    if not isinstance(data, Sequence):
        raise NamecheapIMAPSourceError("IMAP UID FETCH returned an invalid response")
    payloads: list[bytes] = []
    for item in data:
        if isinstance(item, tuple) and len(item) >= 2 and isinstance(item[1], bytes):
            payloads.append(item[1])
    if len(payloads) != 1 or not payloads[0]:
        raise NamecheapIMAPSourceError("IMAP UID FETCH did not return exactly one message")
    return payloads[0]


def _message_id(raw: bytes) -> str:
    try:
        message = BytesParser(policy=policy.default).parsebytes(raw, headersonly=True)
    except Exception as exc:
        raise NamecheapIMAPSourceError("provider message headers cannot be parsed") from exc
    try:
        return MailCorrespondenceStore._message_id(message.get("Message-ID"), "Message-ID")
    except CorrespondenceStoreError as exc:
        raise NamecheapIMAPSourceError("provider message lacks a canonical Message-ID") from exc


def _provider_original_recipient(raw: bytes, expected_domain: str) -> dict[str, str]:
    """Return one authoritative provider recipient or fail closed.

    The accepted live Namecheap header canary established that real delivered mail can
    expose both X-Original-To and Delivered-To. Prefer X-Original-To because a Catch-All
    delivery may set Delivered-To to the physical mailbox while X-Original-To preserves
    the logical SMTP recipient. If the stronger header is present but ambiguous/invalid,
    do not silently fall through to weaker evidence.
    """

    try:
        message = BytesParser(policy=policy.default).parsebytes(raw, headersonly=True)
    except Exception as exc:
        raise NamecheapIMAPSourceError("provider message headers cannot be parsed") from exc

    for header_name in _ORIGINAL_RECIPIENT_HEADERS:
        values = message.get_all(header_name, [])
        if not values:
            continue
        parsed = [address for _, address in getaddresses(values) if address]
        if len(parsed) != 1:
            raise NamecheapIMAPSourceError("provider original-recipient evidence is ambiguous")
        try:
            address = MailCorrespondenceStore._address(parsed[0], header_name)
        except CorrespondenceStoreError as exc:
            raise NamecheapIMAPSourceError("provider original-recipient evidence is invalid") from exc
        domain = address.rsplit("@", 1)[1].casefold()
        if domain != expected_domain.casefold():
            raise NamecheapIMAPSourceError("provider original-recipient domain is unexpected")
        return {"address": address, "header": header_name}

    raise NamecheapIMAPSourceError("provider original-recipient evidence is unavailable")


class _RecipientBoundStore:
    """Proxy a store while binding one provider-authoritative inbound recipient."""

    def __init__(self, store: MailCorrespondenceStore, recipient: str) -> None:
        self._store = store
        self._recipient = recipient
        self.source_scope = store.source_scope
        self.source_authoritative = store.source_authoritative

    def read_message(self, message_id: str):
        return self._store.read_message(message_id)

    def ingest(self, payload: dict):
        rebound = dict(payload)
        rebound["recipients"] = [self._recipient]
        return self._store.ingest(rebound)


def _already_ingested(store: MailCorrespondenceStore, message_id: str) -> bool:
    try:
        existing = store.read_message(message_id)
    except CorrespondenceStoreError as exc:
        if str(exc) == "message not found":
            return False
        raise NamecheapIMAPSourceError(str(exc)) from exc
    provenance = existing.get("provenance", {})
    return bool(
        provenance.get("authoritative")
        and provenance.get("scope") in {"local_native", "production_native"}
    )


def ingest_namecheap_private_email(
    config: NamecheapIMAPConfig,
    store: MailCorrespondenceStore,
    *,
    password_provider: Callable[[], str],
    session_factory: Callable[[], IMAPSession] = _default_session_factory,
) -> dict[str, object]:
    """Read a bounded tail of INBOX and persist new authoritative correspondence.

    Provider/session failures abort the pass. Message-specific RFC822 or original-
    recipient failures are held out of the store and reported by UID without weakening
    validation for safe neighboring messages. The function performs no mailbox mutation
    and never returns the supplied password.
    """

    config.validate()
    if store.source_scope != NAMECHEAP_SCOPE or not store.source_authoritative:
        raise NamecheapIMAPSourceError(
            "provider ingestion requires an authoritative production_native store"
        )

    password = password_provider()
    if not isinstance(password, str) or not password:
        raise NamecheapIMAPSourceError("mailbox credential is unavailable")

    expected_domain = config.username.rsplit("@", 1)[1]
    session: IMAPSession | None = None
    logged_in = False
    try:
        session = session_factory()
        status, _ = session.login(config.username, password)
        _ok(status, "LOGIN")
        logged_in = True
        status, _ = session.select(config.mailbox, readonly=True)
        _ok(status, "SELECT")
        uidvalidity = _uidvalidity(session)
        uids = _search_uids(session)
        selected = uids[-config.max_messages :]

        ingested: list[dict[str, object]] = []
        skipped: list[dict[str, object]] = []
        failed: list[dict[str, object]] = []
        for uid in selected:
            uid_text = uid.decode("ascii")
            raw = _fetch_raw(session, uid)
            try:
                message_id = _message_id(raw)
            except NamecheapIMAPSourceError:
                failed.append({"uid": uid_text, "reason": "invalid_message_id"})
                continue

            if _already_ingested(store, message_id):
                skipped.append(
                    {
                        "uid": uid_text,
                        "message_id": message_id,
                        "reason": "already_ingested",
                    }
                )
                continue

            try:
                recipient = _provider_original_recipient(raw, expected_domain)
            except NamecheapIMAPSourceError:
                failed.append(
                    {
                        "uid": uid_text,
                        "message_id": message_id,
                        "reason": "recipient_evidence_rejected",
                    }
                )
                continue

            try:
                record = normalize_rfc822(
                    raw,
                    _RecipientBoundStore(store, recipient["address"]),
                    direction="inbound",
                )
            except LocalMailSourceError:
                failed.append(
                    {
                        "uid": uid_text,
                        "message_id": message_id,
                        "reason": "normalization_rejected",
                    }
                )
                continue

            ingested.append(
                {
                    "uid": uid_text,
                    "message_id": record["message_id"],
                    "thread_id": record["thread_id"],
                    "recipient_header": recipient["header"],
                    "provenance": record["provenance"],
                    "content_is_untrusted": record["content_is_untrusted"],
                    "send_authorized": record["send_authorized"],
                    "mutation_authorized": record["mutation_authorized"],
                }
            )

        return {
            "contract": "wwcx.namecheap-private-email-read.v1",
            "provider": "namecheap_private_email",
            "endpoint": NAMECHEAP_IMAP_HOST,
            "port": NAMECHEAP_IMAP_PORT,
            "mailbox": config.mailbox,
            "account": config.username,
            "uidvalidity": uidvalidity,
            "selected_count": len(selected),
            "ingested_count": len(ingested),
            "skipped_count": len(skipped),
            "failed_count": len(failed),
            "complete": not failed,
            "ingested": ingested,
            "skipped": skipped,
            "failed": failed,
            "mailbox_read_only": True,
            "network_activity": True,
            "send_authorized": False,
            "mutation_authorized": False,
            "credential_returned": False,
        }
    except (imaplib.IMAP4.error, OSError, ssl.SSLError) as exc:
        raise NamecheapIMAPSourceError("provider IMAP read failed") from exc
    finally:
        password = ""
        if session is not None and logged_in:
            try:
                session.logout()
            except Exception:
                pass
