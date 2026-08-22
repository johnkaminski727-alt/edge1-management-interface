#!/usr/bin/env python3
"""One-shot loopback SMTP -> Mail Room acceptance for Edge1 Mail Gateway v1.

This tool never contacts an external host. It connects only to 127.0.0.1:25, submits
one synthetic message to a configured candidate domain, then verifies that the Postfix
pipe transport persisted exactly one authoritative production_native Mail Room record.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import pwd
import smtplib
import sys
import time
import uuid
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import format_datetime
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
SERVER = ROOT / "server"
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))

from mail_correspondence_store import (  # noqa: E402
    CorrespondenceStoreError,
    MailCorrespondenceStore,
)

CONFIG = ROOT / "config" / "messaging" / "edge1-mail-gateway-v1.json"
STORE = pathlib.Path("/var/lib/wwcx-mail-room/correspondence.sqlite3")
CONTRACT = "wwcx.edge1-mail-gateway-local-acceptance.v1"
EXPECTED_USER = "wwcx-mail-gateway"


class AcceptanceError(RuntimeError):
    pass


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _load_config(path: pathlib.Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("contract") != "wwcx.edge1-mail-gateway.v1":
        raise AcceptanceError("gateway configuration contract is invalid")
    if data.get("activation") != {
        "public_smtp_listener_enabled": False,
        "production_mx_changes_authorized": False,
        "outbound_delivery_enabled": False,
    }:
        raise AcceptanceError("gateway configuration is not safely disabled")
    return data


def _candidate_domain(config: dict[str, Any], requested: str | None) -> str:
    domains = config.get("domains")
    if not isinstance(domains, dict):
        raise AcceptanceError("gateway domain configuration is invalid")
    candidates: list[tuple[int, str]] = []
    for domain, entry in domains.items():
        if not isinstance(entry, dict):
            continue
        if entry.get("mode") == "candidate" and entry.get("catch_all_enabled") is True:
            order = entry.get("migration_order")
            if isinstance(order, int):
                candidates.append((order, str(domain).casefold()))
    candidates.sort()
    candidate_names = [domain for _, domain in candidates]
    if "ww.cx" in candidate_names:
        raise AcceptanceError("ww.cx must remain external in v1")
    if requested:
        value = requested.strip().casefold()
        if value not in candidate_names:
            raise AcceptanceError("requested acceptance domain is not a configured candidate")
        return value
    if not candidate_names:
        raise AcceptanceError("no candidate domain is available")
    return candidate_names[0]


def _reader(path: pathlib.Path) -> MailCorrespondenceStore:
    return MailCorrespondenceStore(
        path,
        source="edge1-mail-gateway-acceptance-reader",
        source_authoritative=False,
        source_scope="synthetic",
        read_only=True,
    )


def _message(recipient: str, now: datetime) -> tuple[str, str, bytes]:
    token = uuid.uuid4().hex[:16]
    message_id = f"<edge1-mail-gateway-acceptance-{token}@ww.cx>"
    sender = "mail-gateway-acceptance@ww.cx"
    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Date"] = format_datetime(now)
    message["Message-ID"] = message_id
    message["Subject"] = "WW.CX Edge1 Mail Gateway local acceptance"
    message.set_content(
        "Synthetic local-only acceptance message. External delivery was not requested.\n"
    )
    return message_id, sender, message.as_bytes()


def _wait_for_record(path: pathlib.Path, message_id: str, timeout: float = 12.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            return _reader(path).read_message(message_id)
        except (CorrespondenceStoreError, OSError) as exc:
            last_error = exc
            time.sleep(0.25)
    raise AcceptanceError("local SMTP message was not persisted by Mail Room") from last_error


def run(*, config_path: pathlib.Path, store_path: pathlib.Path, domain: str | None) -> dict[str, Any]:
    try:
        username = pwd.getpwuid(os.geteuid()).pw_name
    except KeyError as exc:
        raise AcceptanceError("acceptance execution user cannot be resolved") from exc
    if username != EXPECTED_USER:
        raise AcceptanceError(f"acceptance must run as {EXPECTED_USER}")
    if store_path != STORE:
        raise AcceptanceError("acceptance is restricted to the live Mail Room store")
    if not store_path.is_file() or store_path.is_symlink():
        raise AcceptanceError("live Mail Room store is unavailable or unsafe")

    config = _load_config(config_path)
    selected_domain = _candidate_domain(config, domain)
    before = _reader(store_path).status()
    now = datetime.now(timezone.utc)
    recipient = f"acceptance-{uuid.uuid4().hex[:12]}@{selected_domain}"
    message_id, sender, raw = _message(recipient, now)

    try:
        with smtplib.SMTP("127.0.0.1", 25, timeout=5) as client:
            client.ehlo_or_helo_if_needed()
            refused = client.sendmail(sender, [recipient], raw)
    except (OSError, smtplib.SMTPException) as exc:
        raise AcceptanceError("loopback SMTP submission failed") from exc
    if refused:
        raise AcceptanceError("loopback SMTP recipient was refused")

    record = _wait_for_record(store_path, message_id)
    after = _reader(store_path).status()
    if after["record_count"] != before["record_count"] + 1:
        raise AcceptanceError("Mail Room record count did not advance by exactly one")
    if record.get("recipients") != [recipient]:
        raise AcceptanceError("Mail Room recipient does not preserve the SMTP original recipient")
    if record.get("sender") != sender:
        raise AcceptanceError("Mail Room sender does not match acceptance envelope")
    if record.get("provenance") != {
        "source": "edge1-mail-gateway-smtp",
        "scope": "production_native",
        "authoritative": True,
    }:
        raise AcceptanceError("Mail Room provenance is invalid")
    provider_message_id = str(record.get("provider_message_id") or "")
    if not provider_message_id.startswith("postfix:"):
        raise AcceptanceError("Postfix queue correlation is unavailable")
    if record.get("content_is_untrusted") is not True:
        raise AcceptanceError("provider content is not marked untrusted")
    if record.get("mutation_authorized") is not False or record.get("send_authorized") is not False:
        raise AcceptanceError("ingested record unexpectedly grants authority")

    return {
        "contract": CONTRACT,
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "smtp_host": "127.0.0.1",
        "smtp_port": 25,
        "external_network_contact": False,
        "domain": selected_domain,
        "recipient_sha256": _sha256(recipient.casefold()),
        "message_id_sha256": _sha256(message_id),
        "provider_message_id_sha256": _sha256(provider_message_id),
        "record_count_before": before["record_count"],
        "record_count_after": after["record_count"],
        "ingested_count": 1,
        "provenance": record["provenance"],
        "content_output": False,
        "credentials_output": False,
        "mailbox_mutation_authorized": False,
        "mail_send_authorized": False,
        "provider_mutation_authorized": False,
        "public_smtp_listener_authorized": False,
        "production_mx_changes_authorized": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(CONFIG))
    parser.add_argument("--store", default=str(STORE))
    parser.add_argument("--domain")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    if not args.execute:
        print("--execute is required for the one-shot loopback SMTP acceptance", file=sys.stderr)
        return 2
    try:
        result = run(
            config_path=pathlib.Path(args.config).absolute(),
            store_path=pathlib.Path(args.store).absolute(),
            domain=args.domain,
        )
        print(json.dumps(result, sort_keys=True, indent=2))
        return 0
    except (AcceptanceError, CorrespondenceStoreError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
