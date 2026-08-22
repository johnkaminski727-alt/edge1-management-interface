#!/usr/bin/env python3
"""Provider-neutral Edge1 SMTP gateway source for WW.CX Mail Room.

This module performs no network activity. It normalizes raw RFC822 bytes delivered by
an already-authenticated/local MTA path and persists them with authoritative
`production_native` provenance. The SMTP envelope recipient supplied by the MTA is the
recipient authority; visible To/Cc headers never override it.
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
EDGE1_SOURCE = "edge1-mail-gateway-smtp"
EDGE1_SCOPE = "production_native"
MESSAGE_ID_TOKEN_RE = re.compile(r"<[^<>\r\n\s]+@[^<>\r\n\s]+>")
QUEUE_ID_RE = re.compile(r"^[A-Za-z0-9]{5,64}$")


class Edge1MailGatewaySourceError(RuntimeError):
    pass


def open_edge1_store(path: str | Path) -> MailCorrespondenceStore:
    return MailCorrespondenceStore(
        path,
        source=EDGE1_SOURCE,
        source_authoritative=True,
        source_scope=EDGE1_SCOPE,
    )


def _canonical_message_id(value: Any, label: str) -> str:
    try:
        return MailCorrespondenceStore._message_id(value, label)
    except CorrespondenceStoreError as exc:
        raise Edge1MailGatewaySourceError(str(exc)) from exc


def _canonical_address(value: Any, label: str) -> str:
    try:
        return MailCorrespondenceStore._address(value, label)
    except CorrespondenceStoreError as exc:
        raise Edge1MailGatewaySourceError(str(exc)) from exc


def _address_list(values: list[str], label: str) -> list[str]:
    parsed = [address for _, address in getaddresses(values) if address]
    if not parsed:
        raise Edge1MailGatewaySourceError(f"{label} must contain at least one address")
    return [_canonical_address(item, label) for item in parsed]


def _single_sender(message: Message) -> str:
    parsed = _address_list(message.get_all("From", []), "From")
    if len(parsed) != 1:
        raise Edge1MailGatewaySourceError("From must contain exactly one address")
    return parsed[0]


def _date(message: Message) -> str:
    raw = str(message.get("Date", "")).strip()
    if not raw:
        raise Edge1MailGatewaySourceError("Date header is required")
    try:
        parsed = parsedate_to_datetime(raw)
    except (TypeError, ValueError) as exc:
        raise Edge1MailGatewaySourceError("Date header is invalid") from exc
    if parsed is None or parsed.tzinfo is None:
        raise Edge1MailGatewaySourceError("Date header must include a timezone")
    return parsed.isoformat(timespec="seconds")


def _message_ids(value: str | None, label: str) -> list[str]:
    if not value:
        return []
    tokens = MESSAGE_ID_TOKEN_RE.findall(str(value))
    if not tokens:
        raise Edge1MailGatewaySourceError(f"{label} does not contain a canonical Message-ID")
    if len(tokens) > 100:
        raise Edge1MailGatewaySourceError(f"{label} exceeds intake limit")
    return [_canonical_message_id(item, label) for item in tokens]


def _plain_text(message: Message) -> str:
    chunks: list[str] = []
    if message.is_multipart():
        for part in message.walk():
            if part.is_multipart() or part.get_content_disposition() == "attachment":
                continue
            if part.get_content_type() != "text/plain":
                continue
            try:
                content = part.get_content()
            except (LookupError, UnicodeError) as exc:
                raise Edge1MailGatewaySourceError(
                    "text/plain body cannot be decoded safely"
                ) from exc
            if isinstance(content, str):
                chunks.append(content)
    elif message.get_content_type() == "text/plain":
        try:
            content = message.get_content()
        except (LookupError, UnicodeError) as exc:
            raise Edge1MailGatewaySourceError(
                "text/plain body cannot be decoded safely"
            ) from exc
        if isinstance(content, str):
            chunks.append(content)
    else:
        raise Edge1MailGatewaySourceError("gateway intake requires a text/plain body")

    body = "\n".join(chunks)
    if "\x00" in body or len(body) > MAX_BODY_CHARS:
        raise Edge1MailGatewaySourceError("message body exceeds safe persistence bounds")
    return body


def _existing_thread(store: MailCorrespondenceStore, candidates: list[str]) -> str | None:
    for candidate in candidates:
        try:
            return str(store.read_message(candidate)["thread_id"])
        except CorrespondenceStoreError as exc:
            if str(exc) != "message not found":
                raise Edge1MailGatewaySourceError(str(exc)) from exc
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
            raise Edge1MailGatewaySourceError(str(exc)) from exc

    candidates: list[str] = []
    if in_reply_to:
        candidates.append(in_reply_to)
    candidates.extend(reversed(references))
    existing = _existing_thread(store, candidates)
    if existing:
        return existing

    root = references[0] if references else in_reply_to or message_id
    digest = hashlib.sha256(root.encode("utf-8")).hexdigest()[:24].upper()
    return f"THREAD-EDGE1-{digest}"


def _original_recipient_evidence(message: Message) -> list[str]:
    values: list[str] = []
    values.extend(message.get_all("X-Original-To", []))
    values.extend(message.get_all("Delivered-To", []))
    if not values:
        return []
    return _address_list(values, "original recipient evidence")


def _envelope_recipient(message: Message, supplied: str) -> str:
    recipient = _canonical_address(supplied, "envelope recipient")
    evidence = _original_recipient_evidence(message)
    if evidence:
        folded = {item.casefold() for item in evidence}
        if folded != {recipient.casefold()}:
            raise Edge1MailGatewaySourceError(
                "original recipient evidence conflicts with SMTP envelope recipient"
            )
    return recipient


def _queue_id(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not QUEUE_ID_RE.fullmatch(text):
        raise Edge1MailGatewaySourceError("Postfix queue id is invalid")
    return f"postfix:{text}"


def normalize_edge1_rfc822(
    raw: bytes,
    store: MailCorrespondenceStore,
    *,
    envelope_recipient: str,
    queue_id: str | None = None,
) -> dict[str, Any]:
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_RFC822_BYTES:
        raise Edge1MailGatewaySourceError("RFC822 message size is invalid")
    try:
        message = BytesParser(policy=policy.default).parsebytes(raw)
    except Exception as exc:
        raise Edge1MailGatewaySourceError("RFC822 message cannot be parsed") from exc

    recipient = _envelope_recipient(message, envelope_recipient)
    message_id = _canonical_message_id(message.get("Message-ID"), "Message-ID")
    references = _message_ids(message.get("References"), "References")
    reply_ids = _message_ids(message.get("In-Reply-To"), "In-Reply-To")
    if len(reply_ids) > 1:
        raise Edge1MailGatewaySourceError("In-Reply-To must identify at most one parent")
    in_reply_to = reply_ids[0] if reply_ids else None
    if in_reply_to and in_reply_to not in references:
        references.append(in_reply_to)

    subject = str(message.get("Subject", ""))
    if len(subject) > 998 or "\x00" in subject:
        raise Edge1MailGatewaySourceError("Subject exceeds safe persistence bounds")

    payload = {
        "message_id": message_id,
        "provider_message_id": _queue_id(queue_id),
        "provider_thread_id": None,
        "thread_id": _thread_id(message, store, message_id, in_reply_to, references),
        "direction": "inbound",
        "sender": _single_sender(message),
        "recipients": [recipient],
        "subject": subject,
        "body_text": _plain_text(message),
        "in_reply_to": in_reply_to,
        "references": references,
        "occurred_at": _date(message),
    }
    try:
        return store.ingest(payload)
    except CorrespondenceStoreError as exc:
        raise Edge1MailGatewaySourceError(str(exc)) from exc


def ingest_edge1_rfc822_file(
    path: str | Path,
    store: MailCorrespondenceStore,
    *,
    envelope_recipient: str,
    queue_id: str | None = None,
) -> dict[str, Any]:
    target = Path(path).absolute()
    if target.is_symlink() or not target.is_file():
        raise Edge1MailGatewaySourceError("RFC822 input must be a regular non-symlink file")
    size = target.stat().st_size
    if size < 1 or size > MAX_RFC822_BYTES:
        raise Edge1MailGatewaySourceError("RFC822 input size is invalid")
    return normalize_edge1_rfc822(
        target.read_bytes(),
        store,
        envelope_recipient=envelope_recipient,
        queue_id=queue_id,
    )
