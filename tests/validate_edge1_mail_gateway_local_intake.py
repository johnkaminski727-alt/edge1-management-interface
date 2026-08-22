#!/usr/bin/env python3
"""Validate local-only Edge1 Mail Gateway intake and Postfix rendering."""

from __future__ import annotations

import json
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVER = ROOT / "server"
TOOLS = ROOT / "tools" / "messaging"
for entry in (SERVER, TOOLS):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from mail_edge1_gateway_source import (  # noqa: E402
    Edge1MailGatewaySourceError,
    normalize_edge1_rfc822,
    open_edge1_store,
)
from render_edge1_mail_gateway_postfix import RenderError, render  # noqa: E402

CONFIG = ROOT / "config" / "messaging" / "edge1-mail-gateway-v1.json"


def message(*, original_to: str | None = "vendor@creekco.ca", html_only: bool = False) -> bytes:
    lines = [
        b"From: sender@example.test",
        b"To: visible-recipient@example.test",
        b"Date: Sat, 22 Aug 2026 07:30:00 +0000",
        b"Message-ID: <edge1-gateway-root@example.test>",
        b"Subject: Edge1 gateway local intake",
    ]
    if original_to is not None:
        lines.append(f"X-Original-To: {original_to}".encode("ascii"))
        lines.append(f"Delivered-To: {original_to}".encode("ascii"))
    if html_only:
        lines.extend(
            [
                b"Content-Type: text/html; charset=utf-8",
                b"",
                b"<p>not accepted by strict normalization</p>",
                b"",
            ]
        )
    else:
        lines.extend(
            [
                b"Content-Type: text/plain; charset=utf-8",
                b"",
                b"Provider-controlled content remains untrusted.",
                b"",
            ]
        )
    return b"\r\n".join(lines)


def main() -> int:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    rendered = render(config)
    managed = rendered["wwcx-edge1-managed-domains"]
    assert "creekco.ca OK" in managed
    assert "spiritcreekgardens.com OK" in managed
    assert "scgardens.ca OK" in managed
    assert "omegafx.com OK" in managed
    assert "ww.cx" not in managed
    assert "inet_interfaces = loopback-only" in rendered["main.cf.fragment"]
    assert "relay_domains =" in rendered["main.cf.fragment"]
    assert "reject_unauth_destination" in rendered["main.cf.fragment"]
    assert "wwcxmail_destination_recipient_limit = 1" in rendered["main.cf.fragment"]
    assert "message_size_limit = 52428800" in rendered["main.cf.fragment"]
    assert "user=wwcx-mail-gateway" in rendered["master.cf.fragment"]
    assert "flags=ROq" in rendered["master.cf.fragment"]
    assert "edge1_mail_gateway_archive.py" in rendered["master.cf.fragment"]
    assert "edge1_mail_gateway_ingest.py" not in rendered["master.cf.fragment"]
    assert "--recipient ${original_recipient}" in rendered["master.cf.fragment"]
    assert "--recipient ${recipient}" not in rendered["master.cf.fragment"]
    assert "--queue-id ${queue_id}" in rendered["master.cf.fragment"]
    assert "--archive-root /var/lib/wwcx-mail-gateway/inbound" in rendered["master.cf.fragment"]

    unsafe = json.loads(json.dumps(config))
    unsafe["activation"]["public_smtp_listener_enabled"] = True
    try:
        render(unsafe)
        raise AssertionError("public activation configuration rendered unexpectedly")
    except RenderError:
        pass

    ww_candidate = json.loads(json.dumps(config))
    ww_candidate["domains"]["ww.cx"].update(
        {
            "mode": "candidate",
            "migration_order": 5,
            "catch_all_enabled": True,
            "archive_identity": "archive@ww.cx",
        }
    )
    try:
        render(ww_candidate)
        raise AssertionError("ww.cx candidate configuration rendered unexpectedly")
    except RenderError:
        pass

    with tempfile.TemporaryDirectory() as temporary_directory:
        db_path = pathlib.Path(temporary_directory) / "mail" / "correspondence.sqlite3"
        store = open_edge1_store(db_path)

        record = normalize_edge1_rfc822(
            message(),
            store,
            envelope_recipient="vendor@creekco.ca",
            queue_id="ABC123",
        )
        assert record["recipients"] == ["vendor@creekco.ca"]
        assert record["provider_message_id"] == "postfix:ABC123"
        assert record["provenance"] == {
            "source": "edge1-mail-gateway-smtp",
            "scope": "production_native",
            "authoritative": True,
        }
        assert record["content_is_untrusted"] is True
        assert record["mutation_authorized"] is False
        assert record["send_authorized"] is False

        try:
            normalize_edge1_rfc822(
                message(original_to="wrong@creekco.ca"),
                store,
                envelope_recipient="vendor@creekco.ca",
                queue_id="ABC124",
            )
            raise AssertionError("conflicting original-recipient evidence was accepted")
        except Edge1MailGatewaySourceError:
            pass

        second_raw = message(original_to=None).replace(
            b"<edge1-gateway-root@example.test>",
            b"<edge1-gateway-no-header@example.test>",
        )
        second = normalize_edge1_rfc822(
            second_raw,
            store,
            envelope_recipient="anything@omegafx.com",
            queue_id="ABC125",
        )
        assert second["recipients"] == ["anything@omegafx.com"]
        assert second["provenance"]["scope"] == "production_native"

        html_raw = message(original_to="html@creekco.ca", html_only=True).replace(
            b"<edge1-gateway-root@example.test>",
            b"<edge1-gateway-html@example.test>",
        )
        try:
            normalize_edge1_rfc822(
                html_raw,
                store,
                envelope_recipient="html@creekco.ca",
                queue_id="ABC126",
            )
            raise AssertionError("HTML-only gateway message was accepted by strict normalizer")
        except Edge1MailGatewaySourceError:
            pass

        try:
            normalize_edge1_rfc822(
                message(),
                store,
                envelope_recipient="vendor@creekco.ca",
                queue_id="ABC127",
            )
            raise AssertionError("duplicate Message-ID was accepted")
        except Edge1MailGatewaySourceError:
            pass

        status = store.status()
        assert status["record_count"] == 2
        assert status["sources"] == [
            {
                "source": "edge1-mail-gateway-smtp",
                "scope": "production_native",
                "authoritative": True,
                "record_count": 2,
            }
        ]

    print("Edge1 Mail Gateway local-only intake validation passed")
    print("Catch-all recipient authority uses SMTP original recipient")
    print("One-recipient pipe delivery is required for exact attribution")
    print("Postfix transport now enters durable raw archive before normalization")
    print("Conflicting original-recipient evidence still fails strict normalization")
    print("Postfix rendering remains loopback-only and relay-denying")
    print("ww.cx remains excluded from v1 managed-domain rendering")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
