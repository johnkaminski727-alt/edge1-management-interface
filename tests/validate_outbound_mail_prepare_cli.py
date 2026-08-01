#!/usr/bin/env python3
"""Repository validation for the no-send outbound message preparation CLI."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[1]
CLI = ROOT / "tools" / "outbound_mail_prepare.py"


def run_cli(arguments: list[str], payload: dict | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CLI), *arguments],
        cwd=ROOT,
        input=None if payload is None else json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
    )


def sample_request() -> dict:
    return {
        "from_address": "contact@creekco.ca",
        "to": ["records@example.com", "manager@example.com"],
        "cc": [],
        "bcc": [],
        "subject": "Controlled records request",
        "body": "Hello,\n\nPlease provide the requested records.\n",
        "message_class": "business_correspondence",
        "signer_name": "John Kaminski",
        "signer_title": "Authorized Representative",
        "case_id": "TEST-MATTER-001",
        "action_id": "TEST-ACTION-001",
        "mailing_address": "151 2 Street South, Invermay, SK",
        "reply_to": "contact@creekco.ca",
    }


assert CLI.is_file(), CLI
source = CLI.read_text(encoding="utf-8")
for required in (
    "prepared_not_sent",
    "external_delivery_attempted",
    "validate_from_address",
    "action_token_sha256",
    "outbound_mail_prepare_cli",
):
    assert required in source, required
assert "smtplib" not in source
assert "requests." not in source
assert "urllib.request" not in source

example = run_cli(["--example"])
assert example.returncode == 0, example.stderr
example_payload = json.loads(example.stdout)
assert example_payload["from_address"] == "john@ww.cx"
assert example_payload["message_class"] == "business_correspondence"

with tempfile.TemporaryDirectory() as temporary_directory:
    temporary = pathlib.Path(temporary_directory)
    output_path = temporary / "prepared.json"
    body_path = temporary / "prepared.txt"
    audit_path = temporary / "audit.jsonl"

    result = run_cli(
        [
            "--pretty",
            "--output",
            str(output_path),
            "--body-output",
            str(body_path),
            "--audit-jsonl",
            str(audit_path),
        ],
        sample_request(),
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""

    artifact = json.loads(output_path.read_text(encoding="utf-8"))
    body = body_path.read_text(encoding="utf-8")
    audit_lines = audit_path.read_text(encoding="utf-8").splitlines()
    assert len(audit_lines) == 1
    audit = json.loads(audit_lines[0])

    assert artifact["contract"] == "wwcx.outbound-mail-prepared.v1"
    assert artifact["status"] == "prepared_not_sent"
    assert artifact["network_activity"] is False
    assert artifact["external_delivery_attempted"] is False
    assert artifact["request"]["from_address"] == "contact@creekco.ca"
    assert artifact["audit_record"]["from_address"] == "contact@creekco.ca"
    assert artifact["headers"]["X-WWCX-Tracking"] == "disclosed-action-link; no-hidden-pixel"
    assert artifact["headers"]["X-WWCX-Case-ID"] == "TEST-MATTER-001"
    assert artifact["headers"]["X-WWCX-Action-ID"] == "TEST-ACTION-001"
    assert len(artifact["action_token_sha256"]) == 64
    assert "action_token" not in artifact
    assert "contact@creekco.ca" in body
    assert "151 2 Street South, Invermay, SK" in body
    assert "Access to the linked correspondence record may be logged" in body
    assert "does not create confidentiality, privilege" in body
    assert body == artifact["body"]

    raw_token = artifact["action_url"].rsplit("/", 1)[-1]
    audit_serialized = json.dumps(audit, sort_keys=True)
    assert raw_token not in audit_serialized
    assert sample_request()["body"] not in audit_serialized
    assert audit["source"] == "outbound_mail_prepare_cli"
    assert audit["delivery_status"] == "prepared_not_sent"

invalid_sender = sample_request()
invalid_sender["from_address"] = "attacker@example.net"
invalid = run_cli([], invalid_sender)
assert invalid.returncode == 2
assert "from_address domain is not allowed" in invalid.stderr

commercial = sample_request()
commercial["message_class"] = "commercial"
commercial_result = run_cli([], commercial)
assert commercial_result.returncode == 2
assert "unsubscribe_url" in commercial_result.stderr

print("Outbound mail preparation CLI validation passed")
print("No network or delivery operation is available through this adapter")
