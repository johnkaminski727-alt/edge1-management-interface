#!/usr/bin/env python3
"""Durable raw RFC822 intake for the Edge1 Mail Gateway.

Postfix invokes this command once per original recipient. The command's delivery
contract is deliberately archive-first: once the raw message and initial metadata are
durable under the managed per-domain archive, parser/normalizer failures are recorded
as held work and do not turn an otherwise received message into an SMTP delivery
failure.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import sys
import tempfile
from datetime import datetime, timezone
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
SERVER = ROOT / "server"
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))

from mail_edge1_gateway_source import (  # noqa: E402
    Edge1MailGatewaySourceError,
    normalize_edge1_rfc822,
    open_edge1_store,
)

DEFAULT_CONFIG = ROOT / "config" / "messaging" / "edge1-mail-gateway-v1.json"
DEFAULT_ARCHIVE_ROOT = pathlib.Path("/var/lib/wwcx-mail-gateway/inbound")
DEFAULT_STORE = pathlib.Path("/var/lib/wwcx-mail-room/correspondence.sqlite3")
ARCHIVE_CONTRACT = "wwcx.edge1-mail-gateway-raw-archive.v1"
MAX_RAW_BYTES = 50 * 1024 * 1024
QUEUE_ID_RE = re.compile(r"^[A-Za-z0-9]{5,64}$")
DOMAIN_RE = re.compile(r"^[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?$")


class ArchiveError(RuntimeError):
    pass


def _load_config(path: pathlib.Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("contract") != "wwcx.edge1-mail-gateway.v1":
        raise ArchiveError("gateway configuration contract is invalid")
    if data.get("activation") != {
        "public_smtp_listener_enabled": False,
        "production_mx_changes_authorized": False,
        "outbound_delivery_enabled": False,
    }:
        raise ArchiveError("gateway configuration is not safely disabled")
    return data


def _managed_domains(config: dict[str, Any]) -> set[str]:
    domains = config.get("domains")
    if not isinstance(domains, dict):
        raise ArchiveError("gateway domain configuration is invalid")
    result: set[str] = set()
    for domain, entry in domains.items():
        value = str(domain).casefold()
        if not DOMAIN_RE.fullmatch(value) or ".." in value:
            raise ArchiveError("gateway domain name is invalid")
        if not isinstance(entry, dict):
            raise ArchiveError("gateway domain entry is invalid")
        if entry.get("mode") == "candidate" and entry.get("catch_all_enabled") is True:
            result.add(value)
    if "ww.cx" in result:
        raise ArchiveError("ww.cx must remain external in v1")
    return result


def _recipient(value: str, managed_domains: set[str]) -> tuple[str, str]:
    text = str(value).strip()
    if text.count("@") != 1 or any(char.isspace() for char in text):
        raise ArchiveError("envelope recipient is invalid")
    local, domain = text.rsplit("@", 1)
    domain = domain.casefold()
    if not local or domain not in managed_domains:
        raise ArchiveError("envelope recipient domain is not enabled for local intake")
    return text, domain


def _queue_id(value: str) -> str:
    text = str(value).strip()
    if not QUEUE_ID_RE.fullmatch(text):
        raise ArchiveError("Postfix queue id is invalid")
    return text


def _read_raw() -> bytes:
    raw = sys.stdin.buffer.read(MAX_RAW_BYTES + 1)
    if not raw:
        raise ArchiveError("RFC822 message is empty")
    if len(raw) > MAX_RAW_BYTES:
        raise ArchiveError("RFC822 message exceeds raw archive limit")
    return raw


def _secure_dir(path: pathlib.Path) -> None:
    if path.exists() and (not path.is_dir() or path.is_symlink()):
        raise ArchiveError("archive path is not a safe directory")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink():
        raise ArchiveError("archive directory may not be a symlink")
    path.chmod(0o700)


def _atomic_bytes(path: pathlib.Path, payload: bytes) -> None:
    if path.exists():
        if path.is_symlink() or not path.is_file():
            raise ArchiveError("archive target is unsafe")
        if path.read_bytes() != payload:
            raise ArchiveError("archive target collision detected")
        return
    fd, temporary = tempfile.mkstemp(prefix=".tmp-", dir=str(path.parent))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb", closefd=True) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        path.chmod(0o600)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _atomic_json(path: pathlib.Path, payload: dict[str, Any]) -> None:
    rendered = (json.dumps(payload, sort_keys=True, indent=2) + "\n").encode("utf-8")
    fd, temporary = tempfile.mkstemp(prefix=".tmp-", dir=str(path.parent))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb", closefd=True) as handle:
            handle.write(rendered)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        path.chmod(0o600)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _archive_paths(root: pathlib.Path, domain: str, queue_id: str, recipient: str) -> tuple[pathlib.Path, pathlib.Path]:
    recipient_hash = hashlib.sha256(recipient.casefold().encode("utf-8")).hexdigest()[:16]
    directory = root / domain / f"{queue_id}-{recipient_hash}"
    _secure_dir(root)
    _secure_dir(root / domain)
    _secure_dir(directory)
    return directory / "message.eml", directory / "metadata.json"


def archive_and_normalize(
    *,
    raw: bytes,
    recipient: str,
    queue_id: str,
    config_path: pathlib.Path,
    archive_root: pathlib.Path,
    store_path: pathlib.Path,
) -> dict[str, Any]:
    config = _load_config(config_path)
    canonical_recipient, domain = _recipient(recipient, _managed_domains(config))
    canonical_queue = _queue_id(queue_id)
    raw_sha256 = hashlib.sha256(raw).hexdigest()
    message_path, metadata_path = _archive_paths(
        archive_root, domain, canonical_queue, canonical_recipient
    )

    _atomic_bytes(message_path, raw)
    metadata: dict[str, Any] = {
        "contract": ARCHIVE_CONTRACT,
        "archived_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "domain": domain,
        "envelope_recipient": canonical_recipient,
        "postfix_queue_id": canonical_queue,
        "rfc822_sha256": raw_sha256,
        "size_bytes": len(raw),
        "message_file": "message.eml",
        "normalization": {"status": "pending"},
        "content_is_untrusted": True,
        "mail_send_authorized": False,
        "mailbox_mutation_authorized": False,
        "provider_mutation_authorized": False,
    }
    _atomic_json(metadata_path, metadata)

    # Durable raw archival is the delivery boundary. Normalization is best-effort
    # processing after that boundary and must not turn supported raw mail into a
    # Postfix delivery failure.
    try:
        record = normalize_edge1_rfc822(
            raw,
            open_edge1_store(store_path),
            envelope_recipient=canonical_recipient,
            queue_id=canonical_queue,
        )
        metadata["normalization"] = {
            "status": "ingested",
            "message_id_sha256": hashlib.sha256(
                str(record["message_id"]).encode("utf-8")
            ).hexdigest(),
            "thread_id_sha256": hashlib.sha256(
                str(record["thread_id"]).encode("utf-8")
            ).hexdigest(),
        }
    except (Edge1MailGatewaySourceError, OSError, ValueError) as exc:
        metadata["normalization"] = {
            "status": "held",
            "reason": str(exc)[:240],
        }

    try:
        _atomic_json(metadata_path, metadata)
    except (ArchiveError, OSError):
        # The initial pending metadata and raw bytes are already durable. Keep the
        # transport successful so Postfix does not redeliver an archived message.
        pass

    return {
        "contract": ARCHIVE_CONTRACT,
        "status": "archived",
        "domain": domain,
        "postfix_queue_id": canonical_queue,
        "rfc822_sha256": raw_sha256,
        "size_bytes": len(raw),
        "archive_directory": str(message_path.parent),
        "normalization_status": metadata["normalization"]["status"],
        "content_output": False,
        "credentials_output": False,
        "mail_send_authorized": False,
        "mailbox_mutation_authorized": False,
        "provider_mutation_authorized": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--archive-root", default=str(DEFAULT_ARCHIVE_ROOT))
    parser.add_argument("--store", default=str(DEFAULT_STORE))
    parser.add_argument("--recipient", required=True)
    parser.add_argument("--queue-id", required=True)
    parser.add_argument("--stdin", action="store_true")
    args = parser.parse_args()
    if not args.stdin:
        print("--stdin is required for Postfix pipe intake", file=sys.stderr)
        return 2
    try:
        result = archive_and_normalize(
            raw=_read_raw(),
            recipient=args.recipient,
            queue_id=args.queue_id,
            config_path=pathlib.Path(args.config).absolute(),
            archive_root=pathlib.Path(args.archive_root).absolute(),
            store_path=pathlib.Path(args.store).absolute(),
        )
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    except (ArchiveError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
