#!/usr/bin/env python3
"""Run an explicitly authorized, header-only Namecheap Private Email IMAP canary.

The default mode is audit-only and performs no network activity. A live run requires
``--execute`` plus a short-lived private authorization file and runtime credentials in
environment variables. The canary selects INBOX read-only and fetches headers only with
BODY.PEEK[HEADER]; it never fetches message bodies, changes mailbox state, writes the
Mail Room store, or sends mail.
"""

from __future__ import annotations

import argparse
import hashlib
import imaplib
import json
import os
import pathlib
import re
import ssl
import stat
import sys
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from typing import Any, Callable, Mapping, Protocol, Sequence

ROOT = pathlib.Path(__file__).resolve().parents[2]
SERVER = ROOT / "server"
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))

from mail_namecheap_imap_source import NAMECHEAP_IMAP_HOST, NAMECHEAP_IMAP_PORT

AUTH_CONTRACT = "wwcx.namecheap-imap-read-canary-authorization.v1"
RESULT_CONTRACT = "wwcx.namecheap-imap-read-canary-result.v1"
MAX_AUTHORIZATION_SECONDS = 24 * 60 * 60
MAX_CANARY_MESSAGES = 5
USERNAME_ENV = "WWCX_NAMECHEAP_IMAP_USERNAME"
PASSWORD_ENV = "WWCX_NAMECHEAP_IMAP_PASSWORD"
_UID_RE = re.compile(rb"^[1-9][0-9]*$")
_DELIVERY_HEADERS = (
    "delivered-to",
    "x-original-to",
    "envelope-to",
    "x-envelope-to",
    "x-delivered-to",
    "original-recipient",
)


class NamecheapIMAPCanaryError(RuntimeError):
    """Raised for a safe, bounded canary failure."""


class IMAPSession(Protocol):
    def login(self, user: str, password: str): ...
    def select(self, mailbox: str = "INBOX", readonly: bool = False): ...
    def uid(self, command: str, *args): ...
    def response(self, code: str): ...
    def logout(self): ...


def _sha256(value: str | bytes) -> str:
    payload = value if isinstance(value, bytes) else value.encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _load_json(path: pathlib.Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise NamecheapIMAPCanaryError(f"unable to read {label}") from exc
    if not isinstance(value, dict):
        raise NamecheapIMAPCanaryError(f"{label} must be a JSON object")
    return value


def _private_regular_file(path: pathlib.Path, label: str) -> None:
    if not path.is_file() or path.is_symlink():
        raise NamecheapIMAPCanaryError(f"{label} is absent or unsafe")
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise NamecheapIMAPCanaryError(f"{label} permissions are too broad")


def _inside_repo(path: pathlib.Path) -> bool:
    resolved = path.resolve()
    repo = ROOT.resolve()
    return resolved == repo or repo in resolved.parents


def _authorization_expiry(value: Any, *, now: datetime | None = None) -> str:
    try:
        expires = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise NamecheapIMAPCanaryError("IMAP canary authorization expiry is invalid") from exc
    if expires.tzinfo is None:
        raise NamecheapIMAPCanaryError("IMAP canary authorization expiry lacks a timezone")
    current = datetime.now(timezone.utc) if now is None else now.astimezone(timezone.utc)
    remaining = (expires.astimezone(timezone.utc) - current).total_seconds()
    if remaining <= 0:
        raise NamecheapIMAPCanaryError("IMAP canary authorization has expired")
    if remaining > MAX_AUTHORIZATION_SECONDS:
        raise NamecheapIMAPCanaryError("IMAP canary authorization window exceeds 24 hours")
    return expires.astimezone(timezone.utc).isoformat(timespec="seconds")


def validate_authorization_structure(
    authorization: dict[str, Any], *, now: datetime | None = None
) -> dict[str, Any]:
    expected = {
        "contract",
        "provider_read_canary_authorized",
        "expected_host_sha256",
        "expected_port",
        "expected_username_sha256",
        "mailbox",
        "max_messages",
        "expires_at",
        "message_body_fetch_authorized",
        "mailbox_mutation_authorized",
        "store_write_authorized",
        "mail_send_authorized",
    }
    if set(authorization) != expected:
        raise NamecheapIMAPCanaryError("IMAP canary authorization keys are invalid")
    if authorization["contract"] != AUTH_CONTRACT:
        raise NamecheapIMAPCanaryError("IMAP canary authorization contract is unsupported")
    if authorization["provider_read_canary_authorized"] is not True:
        raise NamecheapIMAPCanaryError("provider read canary is not authorized")
    if authorization["expected_host_sha256"] != _sha256(NAMECHEAP_IMAP_HOST):
        raise NamecheapIMAPCanaryError("authorized IMAP host is not Namecheap Private Email")
    if authorization["expected_port"] != NAMECHEAP_IMAP_PORT:
        raise NamecheapIMAPCanaryError("authorized IMAP port is invalid")
    if authorization["mailbox"] != "INBOX":
        raise NamecheapIMAPCanaryError("only INBOX may be inspected")
    if not isinstance(authorization["max_messages"], int) or not 1 <= authorization["max_messages"] <= MAX_CANARY_MESSAGES:
        raise NamecheapIMAPCanaryError(
            f"IMAP canary max_messages must be between 1 and {MAX_CANARY_MESSAGES}"
        )
    for key in (
        "message_body_fetch_authorized",
        "mailbox_mutation_authorized",
        "store_write_authorized",
        "mail_send_authorized",
    ):
        if authorization[key] is not False:
            raise NamecheapIMAPCanaryError("IMAP canary authorization permits prohibited activity")
    expected_username_sha256 = str(authorization["expected_username_sha256"])
    if not re.fullmatch(r"[0-9a-f]{64}", expected_username_sha256):
        raise NamecheapIMAPCanaryError("authorized username hash is invalid")
    return {
        "expires_at": _authorization_expiry(authorization["expires_at"], now=now),
        "max_messages": authorization["max_messages"],
        "expected_username_sha256": expected_username_sha256,
    }


def load_runtime_settings(environment: Mapping[str, str] | None = None) -> dict[str, str]:
    source = os.environ if environment is None else environment
    username = str(source.get(USERNAME_ENV, "")).strip()
    password = str(source.get(PASSWORD_ENV, ""))
    if not username or username.count("@") != 1 or any(character.isspace() for character in username):
        raise NamecheapIMAPCanaryError("IMAP username is unavailable or invalid")
    if not password or len(password) > 4096:
        raise NamecheapIMAPCanaryError("IMAP credential is unavailable or invalid")
    return {"username": username, "password": password}


def validate_runtime_binding(
    authorization: dict[str, Any], settings: dict[str, str], *, now: datetime | None = None
) -> dict[str, Any]:
    status = validate_authorization_structure(authorization, now=now)
    if status["expected_username_sha256"] != _sha256(settings["username"]):
        raise NamecheapIMAPCanaryError("IMAP username does not match authorization")
    return status


def _default_session_factory() -> IMAPSession:
    return imaplib.IMAP4_SSL(
        NAMECHEAP_IMAP_HOST,
        NAMECHEAP_IMAP_PORT,
        ssl_context=ssl.create_default_context(),
        timeout=20,
    )


def _ok(status: Any, label: str) -> None:
    if str(status).upper() != "OK":
        raise NamecheapIMAPCanaryError(f"IMAP {label} failed")


def _uidvalidity(session: IMAPSession) -> str | None:
    response = session.response("UIDVALIDITY")
    if not response or len(response) < 2 or not response[1]:
        return None
    raw = response[1][0]
    text = raw.decode("ascii", "strict").strip() if isinstance(raw, bytes) else str(raw).strip()
    return text if text.isdigit() else None


def _search_uids(session: IMAPSession) -> list[bytes]:
    status, data = session.uid("SEARCH", None, "ALL")
    _ok(status, "UID SEARCH")
    if not data:
        return []
    first = data[0]
    if not isinstance(first, bytes):
        raise NamecheapIMAPCanaryError("IMAP UID SEARCH returned an invalid response")
    uids = first.split()
    if any(not _UID_RE.fullmatch(uid) for uid in uids):
        raise NamecheapIMAPCanaryError("IMAP UID SEARCH returned an invalid UID")
    return sorted(uids, key=lambda value: int(value))


def _fetch_headers(session: IMAPSession, uid: bytes) -> bytes:
    status, data = session.uid("FETCH", uid, "(BODY.PEEK[HEADER])")
    _ok(status, "UID FETCH header")
    if not isinstance(data, Sequence):
        raise NamecheapIMAPCanaryError("IMAP UID FETCH header returned an invalid response")
    payloads = [
        item[1]
        for item in data
        if isinstance(item, tuple) and len(item) >= 2 and isinstance(item[1], bytes)
    ]
    if len(payloads) != 1 or not payloads[0]:
        raise NamecheapIMAPCanaryError("IMAP UID FETCH header did not return exactly one header block")
    return payloads[0]


def _summarize_headers(uid: bytes, raw_headers: bytes) -> dict[str, Any]:
    try:
        message = BytesParser(policy=policy.default).parsebytes(raw_headers, headersonly=True)
    except Exception as exc:
        raise NamecheapIMAPCanaryError("provider header block cannot be parsed") from exc
    names = {str(name).casefold() for name in message.keys()}
    message_id = str(message.get("Message-ID", "")).strip()
    return {
        "uid_sha256": _sha256(uid),
        "message_id_sha256": _sha256(message_id) if message_id else None,
        "message_id_present": bool(message_id),
        "to_present": "to" in names,
        "cc_present": "cc" in names,
        "bcc_present": "bcc" in names,
        "delivery_header_names_present": [name for name in _DELIVERY_HEADERS if name in names],
    }


def run_canary(
    settings: dict[str, str],
    authorization: dict[str, Any],
    *,
    session_factory: Callable[[], IMAPSession] = _default_session_factory,
    now: datetime | None = None,
) -> dict[str, Any]:
    auth_status = validate_runtime_binding(authorization, settings, now=now)
    session: IMAPSession | None = None
    logged_in = False
    try:
        session = session_factory()
        status, _ = session.login(settings["username"], settings["password"])
        _ok(status, "LOGIN")
        logged_in = True
        status, _ = session.select("INBOX", readonly=True)
        _ok(status, "SELECT")
        uidvalidity = _uidvalidity(session)
        selected = _search_uids(session)[-auth_status["max_messages"] :]
        messages = [_summarize_headers(uid, _fetch_headers(session, uid)) for uid in selected]
    except NamecheapIMAPCanaryError:
        raise
    except (imaplib.IMAP4.error, OSError, ssl.SSLError) as exc:
        raise NamecheapIMAPCanaryError("provider IMAP read canary transport failed") from exc
    finally:
        settings["password"] = ""
        if session is not None and logged_in:
            try:
                session.logout()
            except Exception:
                pass

    checked_at = datetime.now(timezone.utc) if now is None else now.astimezone(timezone.utc)
    return {
        "contract": RESULT_CONTRACT,
        "checked_at": checked_at.isoformat(timespec="seconds"),
        "provider": "namecheap_private_email",
        "host_sha256": _sha256(NAMECHEAP_IMAP_HOST),
        "port": NAMECHEAP_IMAP_PORT,
        "username_sha256": _sha256(settings["username"]),
        "mailbox": "INBOX",
        "authorization_expires_at": auth_status["expires_at"],
        "uidvalidity": uidvalidity,
        "selected_count": len(messages),
        "messages": messages,
        "network_activity": True,
        "tls_verification_required": True,
        "mailbox_read_only": True,
        "message_body_fetched": False,
        "mailbox_mutation_authorized": False,
        "store_write_authorized": False,
        "mail_send_authorized": False,
        "credentials_output": False,
    }


def audit_result(authorization: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    status = validate_authorization_structure(authorization, now=now)
    return {
        "contract": RESULT_CONTRACT,
        "mode": "audit_only",
        "provider": "namecheap_private_email",
        "host_sha256": _sha256(NAMECHEAP_IMAP_HOST),
        "port": NAMECHEAP_IMAP_PORT,
        "mailbox": "INBOX",
        "max_messages": status["max_messages"],
        "authorization_expires_at": status["expires_at"],
        "network_activity": False,
        "credential_read": False,
        "message_body_fetched": False,
        "mailbox_mutation_authorized": False,
        "store_write_authorized": False,
        "mail_send_authorized": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authorization", type=pathlib.Path, required=True)
    parser.add_argument("--output", type=pathlib.Path)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if _inside_repo(args.authorization):
        print("refusing IMAP canary authorization inside the Git working tree", file=sys.stderr)
        return 2
    if args.output is not None and _inside_repo(args.output):
        print("refusing IMAP canary output inside the Git working tree", file=sys.stderr)
        return 2
    try:
        _private_regular_file(args.authorization, "IMAP canary authorization")
        authorization = _load_json(args.authorization, "IMAP canary authorization")
        if args.execute:
            result = run_canary(load_runtime_settings(), authorization)
        else:
            result = audit_result(authorization)
    except NamecheapIMAPCanaryError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    rendered = json.dumps(
        result,
        indent=2 if args.pretty else None,
        sort_keys=True,
        separators=None if args.pretty else (",", ":"),
    ) + "\n"
    if args.output is None:
        sys.stdout.write(rendered)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        os.chmod(args.output, 0o600)
        print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
