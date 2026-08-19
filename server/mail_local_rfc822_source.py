#!/usr/bin/env python3
"""Private local RFC822 source for WW.CX Mail Room correspondence.

This module is the safe fallback native source when no provider mailbox connector is
available. It reads local RFC822 bytes only, performs no network activity, ignores
attachment bytes, persists bounded text/plain content, and records the source as
`local_native` rather than pretending to be provider production correspondence.
"""

from __future__ import annotations

import hashlib
import re
from email import policy
from email.message import Message
from email.parser import BytesParser
from email.utils import getaddresses, parsedate_to_datetime
from pathlib import Path
from typing import Any

from mail_correspondence_store import (
    MAX_BODY_CHARS,
    CorrespondenceStoreError,
    MailCorrespondenceStore,
)


MAX_RFC822_BYTES = 5 * 1024 * 1024
LOCAL_SOURCE = "local-mailroom-rfc822"
LOCAL_SCOPE = "local_native"
MESSAGE_ID_TOKEN_RE = re.compile(r"<[^<>\r\n\s]+@[^<>\r\n\s]+>")


class LocalMailSourceError(RuntimeError):
    pass


def open_local_store(path: str | Path) -> MailCorrespondenceStore:
    return MailCorrespondenceStore(
        path,
        source=LOCAL_SOURCE,
        source_authoritative=True,
        source_scope=LOCAL_SCOPE,
    )


def _canonical_message_id(value: Any, label: str) -> str:
    try:
        return MailCorrespondenceStore._message_id(value, label)
    except CorrespondenceStoreError as exc:
        raise LocalMailSourceError(str(exc)) from exc


def _address_list(values: list[str], label: str) -> list[str]:
    parsed = [address for _, address in getaddresses(values) if address]
    if not parsed:
        raise LocalMailSourceError(f"{label} must contain at least one address")
    try:
        return [MailCorrespondenceStore._address(item, label) for item in parsed]
    except CorrespondenceStoreError as exc:
        raise LocalMailSourceError(str(exc)) from exc


def _single_sender(message: Message) -> str:
    parsed = _address_list(message.get_all("From", []), "From")
    if len(parsed) != 1:
        raise LocalMailSourceError("From must contain exactly one address")
    return parsed[0]


def _recipients(message: Message) -> list[str]:
    headers: list[str] = []
    headers.extend(message.get_all("To", []))
    headers.extend(message.get_all("Cc", []))
    if not headers:
        headers.extend(message.get_all("Delivered-To", []))
    recipients = _address_list(headers, "recipient")
    deduplicated: list[str] = []
    seen: set[str] = set()
    for recipient in recipients:
        folded = recipient.casefold()
        if folded not in seen:
            seen.add(folded)
            deduplicated.append(recipient)
    if len(deduplicated) > 100:
        raise LocalMailSourceError("recipient count exceeds local intake limit")
    return deduplicated


def _date(message: Message) -> str:
    raw = str(message.get("Date", "")).strip()
    if not raw:
        raise LocalMailSourceError("Date header is required")
    try:
        parsed = parsedate_to_datetime(raw)
    except (TypeError, ValueError) as exc:
        raise LocalMailSourceError("Date header is invalid") from exc
    if parsed is None or parsed.tzinfo is None:
        raise LocalMailSourceError("Date header must include a timezone")
    return parsed.isoformat(timespec="seconds")


def _message_ids(value: str | None, label: str) -> list[str]:
    if not value:
        return []
    tokens = MESSAGE_ID_TOKEN_RE.findall(str(value))
    if not tokens:
        raise LocalMailSourceError(f"{label} does not contain a canonical Message-ID")
    if len(tokens) > 100:
        raise LocalMailSourceError(f"{label} exceeds local intake limit")
    return [_canonical_message_id(item, label) for item in tokens]


def _plain_text(message: Message) -> str:
    chunks: list[str] = []
    if message.is_multipart():
        for part in message.walk():
            if part.is_multipart():
                continue
            if part.get_content_disposition() == "attachment":
                continue
            if part.get_content_type() != "text/plain":
                continue
            try:
                content = part.get_content()
            except (LookupError, UnicodeError) as exc:
                raise LocalMailSourceError("text/plain body cannot be decoded safely") from exc
            if isinstance(content, str):
                chunks.append(content)
    elif message.get_content_type() == "text/plain":
        try:
            content = message.get_content()
        except (LookupError, UnicodeError) as exc:
            raise LocalMailSourceError("text/plain body cannot be decoded safely") from exc
        if isinstance(content, str):
            chunks.append(content)
    else:
        raise LocalMailSourceError("local intake requires a text/plain body")

    body = "\n".join(chunks)
    if "\x00" in body or len(body) > MAX_BODY_CHARS:
        raise LocalMailSourceError("message body exceeds safe persistence bounds")
    return body


def _existing_thread(
    store: MailCorrespondenceStore,
    candidates: list[str],
) -> str | None:
    for candidate in candidates:
        try:
            return str(store.read_message(candidate)["thread_id"])
        except CorrespondenceStoreError as exc:
            if str(exc) != "message not found":
                raise LocalMailSourceError(str(exc)) from exc
    return None


def _thread_id(
    message: Message,
    store: MailCorrespondenceStore,
    message_id: str,
    in_reply_to: str | None,
    references: list[str],
) -> str:
    explicit = str(message.get("X-WWCX-Thread-ID", "")).strip()
    if explicit:
        try:
            return MailCorrespondenceStore._control_id(explicit, "X-WWCX-Thread-ID")
        except CorrespondenceStoreError as exc:
            raise LocalMailSourceError(str(exc)) from exc

    candidates: list[str] = []
    if in_reply_to:
        candidates.append(in_reply_to)
    candidates.extend(reversed(references))
    existing = _existing_thread(store, candidates)
    if existing:
        return existing

    root = references[0] if references else in_reply_to or message_id
    digest = hashlib.sha256(root.encode("utf-8")).hexdigest()[:24].upper()
    return f"THREAD-RFC822-{digest}"


def normalize_rfc822(
    raw: bytes,
    store: MailCorrespondenceStore,
    *,
    direction: str = "inbound",
) -> dict[str, Any]:
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_RFC822_BYTES:
        raise LocalMailSourceError("RFC822 message size is invalid")
    if direction not in {"inbound", "outbound"}:
        raise LocalMailSourceError("direction is invalid")
    try:
        message = BytesParser(policy=policy.default).parsebytes(raw)
    except Exception as exc:
        raise LocalMailSourceError("RFC822 message cannot be parsed") from exc

    message_id = _canonical_message_id(message.get("Message-ID"), "Message-ID")
    references = _message_ids(message.get("References"), "References")
    reply_ids = _message_ids(message.get("In-Reply-To"), "In-Reply-To")
    if len(reply_ids) > 1:
        raise LocalMailSourceError("In-Reply-To must identify at most one parent message")
    in_reply_to = reply_ids[0] if reply_ids else None
    if in_reply_to and in_reply_to not in references:
        references.append(in_reply_to)

    subject = str(message.get("Subject", ""))
    if len(subject) > 998 or "\x00" in subject:
        raise LocalMailSourceError("Subject exceeds safe persistence bounds")

    provider_message_id = str(message.get("X-WWCX-Provider-Message-ID", "")).strip() or None
    provider_thread_id = str(message.get("X-WWCX-Provider-Thread-ID", "")).strip() or None

    payload = {
        "message_id": message_id,
        "provider_message_id": provider_message_id,
        "provider_thread_id": provider_thread_id,
        "thread_id": _thread_id(message, store, message_id, in_reply_to, references),
        "direction": direction,
        "sender": _single_sender(message),
        "recipients": _recipients(message),
        "subject": subject,
        "body_text": _plain_text(message),
        "in_reply_to": in_reply_to,
        "references": references,
        "occurred_at": _date(message),
    }
    try:
        return store.ingest(payload)
    except CorrespondenceStoreError as exc:
        raise LocalMailSourceError(str(exc)) from exc


def ingest_rfc822_file(
    path: str | Path,
    store: MailCorrespondenceStore,
    *,
    direction: str = "inbound",
) -> dict[str, Any]:
    target = Path(path).absolute()
    if target.is_symlink() or not target.is_file():
        raise LocalMailSourceError("RFC822 input must be a regular non-symlink file")
    size = target.stat().st_size
    if size < 1 or size > MAX_RFC822_BYTES:
        raise LocalMailSourceError("RFC822 input size is invalid")
    return normalize_rfc822(target.read_bytes(), store, direction=direction)
