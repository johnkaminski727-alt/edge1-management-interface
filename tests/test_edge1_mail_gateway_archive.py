#!/usr/bin/env python3
"""Validate archive-first Edge1 Mail Gateway delivery semantics."""

from __future__ import annotations

import importlib.util
import json
import pathlib
import stat
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools" / "messaging"
SERVER = ROOT / "server"
for entry in (TOOLS, SERVER):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

ARCHIVE = TOOLS / "edge1_mail_gateway_archive.py"
CONFIG = ROOT / "config" / "messaging" / "edge1-mail-gateway-v1.json"


def load_archive():
    spec = importlib.util.spec_from_file_location("edge1_mail_gateway_archive_tested", ARCHIVE)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load archive module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def raw_message(recipient: str, *, message_id: str, html_only: bool = False) -> bytes:
    lines = [
        b"From: sender@example.test",
        f"To: {recipient}".encode("ascii"),
        f"X-Original-To: {recipient}".encode("ascii"),
        b"Date: Sat, 22 Aug 2026 08:00:00 +0000",
        f"Message-ID: {message_id}".encode("ascii"),
        b"Subject: raw archive validation",
    ]
    if html_only:
        lines.extend(
            [
                b"Content-Type: text/html; charset=utf-8",
                b"",
                b"<p>valid mail that strict normalization may hold</p>",
                b"",
            ]
        )
    else:
        lines.extend(
            [
                b"Content-Type: text/plain; charset=utf-8",
                b"",
                b"archive first, normalize second",
                b"",
            ]
        )
    return b"\r\n".join(lines)


def mode(path: pathlib.Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def main() -> int:
    archive = load_archive()
    assert archive.MAX_RAW_BYTES == 50 * 1024 * 1024

    with tempfile.TemporaryDirectory() as temporary:
        root = pathlib.Path(temporary)
        archive_root = root / "gateway" / "inbound"
        store = root / "mail-room" / "correspondence.sqlite3"

        recipient = "orders@creekco.ca"
        raw = raw_message(recipient, message_id="<archive-one@example.test>")
        first = archive.archive_and_normalize(
            raw=raw,
            recipient=recipient,
            queue_id="ABC123",
            config_path=CONFIG,
            archive_root=archive_root,
            store_path=store,
        )
        assert first["status"] == "archived"
        assert first["domain"] == "creekco.ca"
        assert first["normalization_status"] == "ingested"
        delivery_dir = pathlib.Path(first["archive_directory"])
        assert delivery_dir.parent == archive_root / "creekco.ca"
        message_path = delivery_dir / "message.eml"
        metadata_path = delivery_dir / "metadata.json"
        assert message_path.read_bytes() == raw
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        assert metadata["contract"] == archive.ARCHIVE_CONTRACT
        assert metadata["envelope_recipient"] == recipient
        assert metadata["postfix_queue_id"] == "ABC123"
        assert metadata["normalization"]["status"] == "ingested"
        assert metadata["content_is_untrusted"] is True
        assert metadata["mail_send_authorized"] is False
        assert mode(archive_root) == 0o700
        assert mode(archive_root / "creekco.ca") == 0o700
        assert mode(delivery_dir) == 0o700
        assert mode(message_path) == 0o600
        assert mode(metadata_path) == 0o600

        # Exact Postfix retry must return the existing durable result and must not
        # attempt a duplicate Mail Room insert or rewrite successful metadata.
        before_metadata = metadata_path.read_bytes()
        retry = archive.archive_and_normalize(
            raw=raw,
            recipient=recipient,
            queue_id="ABC123",
            config_path=CONFIG,
            archive_root=archive_root,
            store_path=store,
        )
        assert retry["archive_directory"] == first["archive_directory"]
        assert retry["normalization_status"] == "ingested"
        assert metadata_path.read_bytes() == before_metadata

        # A different recipient on the same Postfix queue receives a separate
        # recipient-specific archive directory.
        second_recipient = "billing@creekco.ca"
        second_raw = raw_message(
            second_recipient, message_id="<archive-two@example.test>"
        )
        second = archive.archive_and_normalize(
            raw=second_raw,
            recipient=second_recipient,
            queue_id="ABC123",
            config_path=CONFIG,
            archive_root=archive_root,
            store_path=store,
        )
        assert second["archive_directory"] != first["archive_directory"]
        assert second["normalization_status"] == "ingested"

        # HTML-only mail is still durably archived. Strict Mail Room parsing may
        # hold it for later processing, but the transport result remains archived.
        html_recipient = "webform@spiritcreekgardens.com"
        html_raw = raw_message(
            html_recipient,
            message_id="<archive-html@example.test>",
            html_only=True,
        )
        held = archive.archive_and_normalize(
            raw=html_raw,
            recipient=html_recipient,
            queue_id="HTML123",
            config_path=CONFIG,
            archive_root=archive_root,
            store_path=store,
        )
        assert held["status"] == "archived"
        assert held["normalization_status"] == "held"
        held_dir = pathlib.Path(held["archive_directory"])
        assert (held_dir / "message.eml").read_bytes() == html_raw
        held_metadata = json.loads((held_dir / "metadata.json").read_text(encoding="utf-8"))
        assert held_metadata["normalization"]["status"] == "held"

        try:
            archive.archive_and_normalize(
                raw=raw_message("outside@ww.cx", message_id="<outside@example.test>"),
                recipient="outside@ww.cx",
                queue_id="OUT123",
                config_path=CONFIG,
                archive_root=archive_root,
                store_path=store,
            )
            raise AssertionError("ww.cx unexpectedly archived through candidate intake")
        except archive.ArchiveError:
            pass
        assert not (archive_root / "ww.cx").exists()

    print("Edge1 Mail Gateway raw archive validation passed")
    print("Raw RFC822 is durable before normalization")
    print("Per-domain and per-recipient queue directories remain separate")
    print("Exact Postfix retries are archive-idempotent")
    print("HTML-only mail is held after archive instead of rejected by delivery")
    print("ww.cx remains outside candidate-domain intake")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
