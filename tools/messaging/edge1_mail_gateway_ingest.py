#!/usr/bin/env python3
"""Local-only Edge1 SMTP -> Mail Room ingestion command.

This command performs no network activity. It is intended for a local MTA pipe
transport after the MTA has accepted a message for an explicitly managed domain.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
SERVER = ROOT / "server"
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))

from mail_edge1_gateway_source import (  # noqa: E402
    MAX_RFC822_BYTES,
    Edge1MailGatewaySourceError,
    normalize_edge1_rfc822,
    open_edge1_store,
)

DEFAULT_CONFIG = ROOT / "config" / "messaging" / "edge1-mail-gateway-v1.json"
DEFAULT_STORE = pathlib.Path("/var/lib/wwcx-mail-room/correspondence.sqlite3")
EVIDENCE_CONTRACT = "wwcx.edge1-mail-gateway-ingestion-evidence.v1"


def _load_json(path: pathlib.Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise Edge1MailGatewaySourceError("gateway configuration must be an object")
    return data


def _managed_candidate_domains(config: dict[str, Any]) -> set[str]:
    if config.get("contract") != "wwcx.edge1-mail-gateway.v1":
        raise Edge1MailGatewaySourceError("gateway configuration contract is invalid")
    activation = config.get("activation")
    if activation != {
        "public_smtp_listener_enabled": False,
        "production_mx_changes_authorized": False,
        "outbound_delivery_enabled": False,
    }:
        raise Edge1MailGatewaySourceError("gateway configuration is not safely disabled")

    result: set[str] = set()
    domains = config.get("domains")
    if not isinstance(domains, dict):
        raise Edge1MailGatewaySourceError("gateway domains are invalid")
    for domain, entry in domains.items():
        if not isinstance(entry, dict):
            raise Edge1MailGatewaySourceError("gateway domain entry is invalid")
        if entry.get("mode") == "candidate" and entry.get("catch_all_enabled") is True:
            result.add(str(domain).casefold())
    if "ww.cx" in result:
        raise Edge1MailGatewaySourceError("ww.cx must remain external in v1")
    return result


def _validate_recipient(recipient: str, managed_domains: set[str]) -> str:
    value = str(recipient).strip()
    if value.count("@") != 1 or any(char.isspace() for char in value):
        raise Edge1MailGatewaySourceError("envelope recipient is invalid")
    _, domain = value.rsplit("@", 1)
    if domain.casefold() not in managed_domains:
        raise Edge1MailGatewaySourceError("envelope recipient domain is not enabled for local intake")
    return value


def _read_raw(path: pathlib.Path | None) -> bytes:
    if path is None:
        raw = sys.stdin.buffer.read(MAX_RFC822_BYTES + 1)
    else:
        target = path.absolute()
        if target.is_symlink() or not target.is_file():
            raise Edge1MailGatewaySourceError("RFC822 input must be a regular non-symlink file")
        raw = target.read_bytes()
    if not raw or len(raw) > MAX_RFC822_BYTES:
        raise Edge1MailGatewaySourceError("RFC822 message size is invalid")
    return raw


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _evidence(record: dict[str, Any], recipient: str) -> dict[str, Any]:
    provenance = record.get("provenance")
    if provenance != {
        "source": "edge1-mail-gateway-smtp",
        "scope": "production_native",
        "authoritative": True,
    }:
        raise Edge1MailGatewaySourceError("ingested record provenance is invalid")
    return {
        "contract": EVIDENCE_CONTRACT,
        "status": "ingested",
        "recipient_sha256": _sha256(recipient.casefold()),
        "message_id_sha256": _sha256(str(record["message_id"])),
        "thread_id_sha256": _sha256(str(record["thread_id"])),
        "provenance": provenance,
        "content_is_untrusted": True,
        "mailbox_mutation_authorized": False,
        "mail_send_authorized": False,
        "provider_mutation_authorized": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--store", default=str(DEFAULT_STORE))
    parser.add_argument("--recipient", required=True)
    parser.add_argument("--queue-id")
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--stdin", action="store_true")
    inputs.add_argument("--rfc822")
    parser.add_argument("--output")
    args = parser.parse_args()

    try:
        config = _load_json(pathlib.Path(args.config))
        recipient = _validate_recipient(
            args.recipient,
            _managed_candidate_domains(config),
        )
        raw = _read_raw(None if args.stdin else pathlib.Path(args.rfc822))
        store = open_edge1_store(pathlib.Path(args.store))
        record = normalize_edge1_rfc822(
            raw,
            store,
            envelope_recipient=recipient,
            queue_id=args.queue_id,
        )
        evidence = _evidence(record, recipient)
        rendered = json.dumps(evidence, sort_keys=True, separators=(",", ":"))
        if args.output:
            output = pathlib.Path(args.output).absolute()
            if output.is_symlink():
                raise Edge1MailGatewaySourceError("evidence output may not be a symlink")
            output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            output.write_text(rendered + "\n", encoding="utf-8")
            output.chmod(0o600)
        print(rendered)
        return 0
    except (OSError, ValueError, json.JSONDecodeError, Edge1MailGatewaySourceError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
