#!/usr/bin/env python3
"""Run one explicitly authorized Namecheap -> Mail Room live ingestion acceptance.

Default mode is audit-only. Live execution is deliberately narrow:

* fixed provider endpoint from ``mail_namecheap_imap_source``;
* exact secret-backed mailbox username hash binding;
* INBOX selected read-only by the provider source;
* exactly one newest full RFC822 message fetched with ``BODY.PEEK[]``;
* at most one new authoritative ``production_native`` record written to the
  existing private Mail Room SQLite store;
* no SMTP, mailbox mutation, provider mutation, DNS change, or persistent polling;
* sanitized evidence only -- no body, subject, addresses, raw Message-ID, UID,
  thread ID, or credential is emitted.

The live database is backed up with SQLite's online backup API before the write.
If post-write validation fails, only the exact row inserted by this invocation is
removed, and only after its immutable provider provenance is verified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import sqlite3
import stat
import sys
from datetime import datetime, timezone
from typing import Any, Callable, Mapping
from urllib.parse import quote

ROOT = pathlib.Path(__file__).resolve().parents[2]
SERVER = ROOT / "server"
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))

from mail_correspondence_store import MailCorrespondenceStore
from mail_namecheap_imap_source import (
    NAMECHEAP_IMAP_HOST,
    NAMECHEAP_IMAP_PORT,
    NAMECHEAP_SCOPE,
    NAMECHEAP_SOURCE,
    NamecheapIMAPConfig,
    NamecheapIMAPSourceError,
    ingest_namecheap_private_email,
    open_namecheap_store,
)

AUTH_CONTRACT = "wwcx.namecheap-imap-ingestion-authorization.v1"
RESULT_CONTRACT = "wwcx.namecheap-imap-ingestion-acceptance.v1"
USERNAME_ENV = "WWCX_NAMECHEAP_IMAP_USERNAME"
PASSWORD_ENV = "WWCX_NAMECHEAP_IMAP_PASSWORD"
LIVE_STORE = pathlib.Path("/var/lib/wwcx-mail-room/correspondence.sqlite3")
MAX_AUTHORIZATION_SECONDS = 60 * 60
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")


class NamecheapIMAPIngestionAcceptanceError(RuntimeError):
    """Raised when the bounded acceptance cannot complete safely."""


def _sha256(value: str | bytes) -> str:
    payload = value if isinstance(value, bytes) else value.encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _load_json(path: pathlib.Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise NamecheapIMAPIngestionAcceptanceError(f"unable to read {label}") from exc
    if not isinstance(value, dict):
        raise NamecheapIMAPIngestionAcceptanceError(f"{label} must be a JSON object")
    return value


def _private_regular_file(path: pathlib.Path, label: str) -> None:
    if not path.is_file() or path.is_symlink():
        raise NamecheapIMAPIngestionAcceptanceError(f"{label} is absent or unsafe")
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise NamecheapIMAPIngestionAcceptanceError(f"{label} permissions are too broad")


def _inside_repo(path: pathlib.Path) -> bool:
    resolved = path.resolve()
    repo = ROOT.resolve()
    return resolved == repo or repo in resolved.parents


def _expiry(value: Any, *, now: datetime | None = None) -> str:
    try:
        expires = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise NamecheapIMAPIngestionAcceptanceError("authorization expiry is invalid") from exc
    if expires.tzinfo is None:
        raise NamecheapIMAPIngestionAcceptanceError("authorization expiry lacks a timezone")
    current = datetime.now(timezone.utc) if now is None else now.astimezone(timezone.utc)
    remaining = (expires.astimezone(timezone.utc) - current).total_seconds()
    if remaining <= 0:
        raise NamecheapIMAPIngestionAcceptanceError("authorization has expired")
    if remaining > MAX_AUTHORIZATION_SECONDS:
        raise NamecheapIMAPIngestionAcceptanceError("authorization window exceeds one hour")
    return expires.astimezone(timezone.utc).isoformat(timespec="seconds")


def validate_authorization(
    authorization: dict[str, Any], *, store_path: pathlib.Path = LIVE_STORE, now: datetime | None = None
) -> dict[str, Any]:
    expected = {
        "contract",
        "provider_ingestion_authorized",
        "expected_host_sha256",
        "expected_port",
        "expected_username_sha256",
        "expected_store_path_sha256",
        "mailbox",
        "max_messages",
        "expires_at",
        "full_message_fetch_authorized",
        "production_native_store_write_authorized",
        "mailbox_mutation_authorized",
        "mail_send_authorized",
        "provider_mutation_authorized",
        "persistent_polling_authorized",
    }
    if set(authorization) != expected:
        raise NamecheapIMAPIngestionAcceptanceError("authorization keys are invalid")
    if authorization["contract"] != AUTH_CONTRACT:
        raise NamecheapIMAPIngestionAcceptanceError("authorization contract is unsupported")
    if authorization["provider_ingestion_authorized"] is not True:
        raise NamecheapIMAPIngestionAcceptanceError("provider ingestion is not authorized")
    if authorization["full_message_fetch_authorized"] is not True:
        raise NamecheapIMAPIngestionAcceptanceError("full-message fetch is not authorized")
    if authorization["production_native_store_write_authorized"] is not True:
        raise NamecheapIMAPIngestionAcceptanceError("production_native store write is not authorized")
    for key in (
        "mailbox_mutation_authorized",
        "mail_send_authorized",
        "provider_mutation_authorized",
        "persistent_polling_authorized",
    ):
        if authorization[key] is not False:
            raise NamecheapIMAPIngestionAcceptanceError("authorization permits prohibited activity")
    if authorization["expected_host_sha256"] != _sha256(NAMECHEAP_IMAP_HOST):
        raise NamecheapIMAPIngestionAcceptanceError("authorized provider host is invalid")
    if authorization["expected_port"] != NAMECHEAP_IMAP_PORT:
        raise NamecheapIMAPIngestionAcceptanceError("authorized provider port is invalid")
    if authorization["expected_store_path_sha256"] != _sha256(str(store_path)):
        raise NamecheapIMAPIngestionAcceptanceError("authorized Mail Room store path is invalid")
    username_hash = str(authorization["expected_username_sha256"])
    if not _HEX_64.fullmatch(username_hash):
        raise NamecheapIMAPIngestionAcceptanceError("authorized username hash is invalid")
    if authorization["mailbox"] != "INBOX" or authorization["max_messages"] != 1:
        raise NamecheapIMAPIngestionAcceptanceError("acceptance is limited to one newest INBOX message")
    return {
        "expires_at": _expiry(authorization["expires_at"], now=now),
        "expected_username_sha256": username_hash,
    }


def load_runtime_settings(environment: Mapping[str, str] | None = None) -> dict[str, str]:
    source = os.environ if environment is None else environment
    username = str(source.get(USERNAME_ENV, "")).strip()
    password = str(source.get(PASSWORD_ENV, ""))
    if not username or username.count("@") != 1 or any(char.isspace() for char in username):
        raise NamecheapIMAPIngestionAcceptanceError("IMAP username is unavailable or invalid")
    if not password or len(password) > 4096:
        raise NamecheapIMAPIngestionAcceptanceError("IMAP credential is unavailable or invalid")
    return {"username": username, "password": password}


def _read_only_store_status(path: pathlib.Path) -> dict[str, Any]:
    return MailCorrespondenceStore(
        path,
        source="namecheap-ingestion-acceptance-read",
        source_authoritative=True,
        source_scope=NAMECHEAP_SCOPE,
        read_only=True,
    ).status()


def _verify_live_store(path: pathlib.Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise NamecheapIMAPIngestionAcceptanceError("live correspondence store is absent or unsafe")
    if path.parent.is_symlink():
        raise NamecheapIMAPIngestionAcceptanceError("live correspondence directory is unsafe")
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise NamecheapIMAPIngestionAcceptanceError("live correspondence store permissions are too broad")
    _read_only_store_status(path)


def _backup_database(source_path: pathlib.Path, backup_root: pathlib.Path) -> tuple[pathlib.Path, str]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = backup_root / stamp
    backup_dir.mkdir(parents=True, mode=0o700, exist_ok=False)
    os.chmod(backup_dir, 0o700)
    backup_path = backup_dir / "correspondence.sqlite3.bak"
    source_uri = f"file:{quote(str(source_path), safe='/')}?mode=ro"
    try:
        with sqlite3.connect(source_uri, uri=True) as source, sqlite3.connect(backup_path) as target:
            source.backup(target)
    except sqlite3.Error as exc:
        raise NamecheapIMAPIngestionAcceptanceError("unable to create SQLite acceptance backup") from exc
    os.chmod(backup_path, 0o600)
    digest = hashlib.sha256(backup_path.read_bytes()).hexdigest()
    return backup_path, digest


def _rollback_exact_insert(path: pathlib.Path, message_id: str) -> bool:
    try:
        with sqlite3.connect(path) as db:
            row = db.execute(
                "SELECT source, source_scope, source_authoritative FROM correspondence WHERE message_id = ?",
                (message_id,),
            ).fetchone()
            if row != (NAMECHEAP_SOURCE, NAMECHEAP_SCOPE, 1):
                return False
            cursor = db.execute(
                "DELETE FROM correspondence WHERE message_id = ? AND source = ? AND source_scope = ? "
                "AND source_authoritative = 1",
                (message_id, NAMECHEAP_SOURCE, NAMECHEAP_SCOPE),
            )
            if cursor.rowcount != 1:
                return False
        os.chmod(path, 0o600)
        return True
    except sqlite3.Error:
        return False


def _sanitized_message(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "uid_sha256": _sha256(str(entry["uid"])),
        "message_id_sha256": _sha256(str(entry["message_id"])),
        "thread_id_sha256": _sha256(str(entry["thread_id"])),
        "provenance": entry["provenance"],
        "content_is_untrusted": bool(entry["content_is_untrusted"]),
        "send_authorized": bool(entry["send_authorized"]),
        "mutation_authorized": bool(entry["mutation_authorized"]),
    }


def run_acceptance(
    settings: dict[str, str],
    authorization: dict[str, Any],
    *,
    store_path: pathlib.Path = LIVE_STORE,
    backup_root: pathlib.Path | None = None,
    session_factory: Callable[[], Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    auth_status = validate_authorization(authorization, store_path=store_path, now=now)
    if _sha256(settings["username"]) != auth_status["expected_username_sha256"]:
        raise NamecheapIMAPIngestionAcceptanceError("IMAP username does not match authorization")
    _verify_live_store(store_path)

    root = backup_root or (store_path.parent / "_acceptance-backups" / "namecheap-imap")
    root.mkdir(parents=True, mode=0o700, exist_ok=True)
    os.chmod(root, 0o700)
    _, backup_sha256 = _backup_database(store_path, root)

    before = _read_only_store_status(store_path)
    writable_store = open_namecheap_store(store_path)
    kwargs: dict[str, Any] = {
        "password_provider": lambda: settings["password"],
    }
    if session_factory is not None:
        kwargs["session_factory"] = session_factory

    inserted_message_id: str | None = None
    try:
        source_result = ingest_namecheap_private_email(
            NamecheapIMAPConfig(username=settings["username"], mailbox="INBOX", max_messages=1),
            writable_store,
            **kwargs,
        )
        if source_result["ingested_count"] == 1:
            inserted = source_result["ingested"][0]
            inserted_message_id = str(inserted["message_id"])
        after = _read_only_store_status(store_path)

        if source_result["selected_count"] != 1:
            raise NamecheapIMAPIngestionAcceptanceError("provider did not expose exactly one selected message")
        if source_result["ingested_count"] != 1 or source_result["skipped_count"] != 0:
            raise NamecheapIMAPIngestionAcceptanceError("acceptance did not produce exactly one new store record")
        if source_result["failed_count"] != 0 or source_result["complete"] is not True:
            raise NamecheapIMAPIngestionAcceptanceError("provider message did not pass strict normalization")
        if after["record_count"] != before["record_count"] + 1:
            raise NamecheapIMAPIngestionAcceptanceError("Mail Room record count did not advance by exactly one")

        inserted = source_result["ingested"][0]
        if inserted["provenance"] != {
            "source": NAMECHEAP_SOURCE,
            "scope": NAMECHEAP_SCOPE,
            "authoritative": True,
        }:
            raise NamecheapIMAPIngestionAcceptanceError("inserted record provenance is invalid")
        if inserted["content_is_untrusted"] is not True:
            raise NamecheapIMAPIngestionAcceptanceError("inserted provider content is not marked untrusted")
        if inserted["send_authorized"] is not False or inserted["mutation_authorized"] is not False:
            raise NamecheapIMAPIngestionAcceptanceError("inserted record unexpectedly grants authority")

        checked_at = datetime.now(timezone.utc) if now is None else now.astimezone(timezone.utc)
        return {
            "contract": RESULT_CONTRACT,
            "checked_at": checked_at.isoformat(timespec="seconds"),
            "provider": "namecheap_private_email",
            "host_sha256": _sha256(NAMECHEAP_IMAP_HOST),
            "port": NAMECHEAP_IMAP_PORT,
            "username_sha256": _sha256(settings["username"]),
            "store_path_sha256": _sha256(str(store_path)),
            "mailbox": "INBOX",
            "selected_count": 1,
            "ingested_count": 1,
            "record_count_before": before["record_count"],
            "record_count_after": after["record_count"],
            "message": _sanitized_message(inserted),
            "backup_created": True,
            "backup_sha256": backup_sha256,
            "full_message_fetched": True,
            "production_native_store_write": True,
            "mailbox_read_only": True,
            "mailbox_mutation_authorized": False,
            "mail_send_authorized": False,
            "provider_mutation_authorized": False,
            "persistent_polling_authorized": False,
            "credentials_output": False,
            "content_output": False,
            "rollback_performed": False,
        }
    except Exception:
        if inserted_message_id is not None:
            if not _rollback_exact_insert(store_path, inserted_message_id):
                raise NamecheapIMAPIngestionAcceptanceError(
                    "acceptance validation failed and exact inserted-row rollback also failed"
                )
        raise
    finally:
        settings["password"] = ""


def audit_result(
    authorization: dict[str, Any], *, store_path: pathlib.Path = LIVE_STORE, now: datetime | None = None
) -> dict[str, Any]:
    status = validate_authorization(authorization, store_path=store_path, now=now)
    return {
        "contract": RESULT_CONTRACT,
        "mode": "audit_only",
        "provider": "namecheap_private_email",
        "host_sha256": _sha256(NAMECHEAP_IMAP_HOST),
        "port": NAMECHEAP_IMAP_PORT,
        "username_sha256": status["expected_username_sha256"],
        "store_path_sha256": _sha256(str(store_path)),
        "mailbox": "INBOX",
        "max_messages": 1,
        "authorization_expires_at": status["expires_at"],
        "network_activity": False,
        "credential_read": False,
        "full_message_fetched": False,
        "production_native_store_write": False,
        "mailbox_mutation_authorized": False,
        "mail_send_authorized": False,
        "provider_mutation_authorized": False,
        "persistent_polling_authorized": False,
    }


def _write_output(path: pathlib.Path, result: dict[str, Any]) -> None:
    if _inside_repo(path):
        raise NamecheapIMAPIngestionAcceptanceError("acceptance evidence may not be written inside Git")
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    os.chmod(path.parent, 0o700)
    path.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authorization", required=True)
    parser.add_argument("--output")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--store", default=str(LIVE_STORE))
    args = parser.parse_args()

    authorization_path = pathlib.Path(args.authorization)
    _private_regular_file(authorization_path, "authorization file")
    if _inside_repo(authorization_path):
        raise NamecheapIMAPIngestionAcceptanceError("authorization file may not be stored inside Git")
    store_path = pathlib.Path(args.store).absolute()
    authorization = _load_json(authorization_path, "authorization file")

    if args.execute:
        settings = load_runtime_settings()
        result = run_acceptance(settings, authorization, store_path=store_path)
    else:
        result = audit_result(authorization, store_path=store_path)

    if args.output:
        output = pathlib.Path(args.output).absolute()
        _write_output(output, result)
        print(str(output))
    else:
        print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (NamecheapIMAPIngestionAcceptanceError, NamecheapIMAPSourceError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)
