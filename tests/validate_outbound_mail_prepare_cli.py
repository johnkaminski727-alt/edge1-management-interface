#!/usr/bin/env python3
"""Repository validation for the identity-aware no-send preparation CLI."""

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
        "from_address": "wrong@example.net",
        "identity_hint": "creekco-contact",
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
    }


assert CLI.is_file(), CLI
source = CLI.read_text(encoding="utf-8")
for required in (
    "prepared_not_sent",
    "external_delivery_attempted",
    "identity_aware_outbound_gateway",
    "mail_identity_registry",
    "sender_selection",
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
assert example_payload["identity_hint"] == "john-wwcx"
assert "from_address" not in example_payload
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
    assert artifact["request"]["reply_to"] == "contact@creekco.ca"
    assert artifact["sender_selection"]["address"] == "contact@creekco.ca"
    assert artifact["sender_selection"]["reason"] == "identity_hint"
    assert artifact["sender_selection"]["from_address_replaced"] is True
    assert artifact["audit_record"]["from_address"] == "contact@creekco.ca"
    assert artifact["headers"]["X-WWCX-Tracking"] == "disclosed-action-link; no-hidden-pixel"
    assert artifact["headers"]["X-WWCX-Case-ID"] == "TEST-MATTER-001"
    assert artifact["headers"]["X-WWCX-Action-ID"] == "TEST-ACTION-001"
    assert len(artifact["action_token_sha256"]) == 64
    assert "action_token" not in artifact
    assert "contact@creekco.ca" in body
    assert "wrong@example.net" not in json.dumps(artifact, sort_keys=True)
    assert "151 2 Street South, Invermay, SK" in body
    assert "Access to the linked correspondence record may be logged" in body
    assert "does not create confidentiality, privilege" in body
    assert body == artifact["body"]

    raw_token = artifact["action_url"].rsplit("/", 1)[-1]
    audit_serialized = json.dumps(audit, sort_keys=True)
    assert raw_token not in audit_serialized
    assert sample_request()["body"] not in audit_serialized
    assert "wrong@example.net" not in audit_serialized
    assert audit["source"] == "outbound_mail_prepare_cli"
    assert audit["delivery_status"] == "prepared_not_sent"
    assert audit["sender_address"] == "contact@creekco.ca"
    assert audit["sender_selection_reason"] == "identity_hint"

spirit = sample_request()
spirit.pop("identity_hint")
spirit["original_recipient"] = "john@spiritcreekgardens.com"
spirit_result = run_cli(["--pretty"], spirit)
assert spirit_result.returncode == 0, spirit_result.stderr
spirit_artifact = json.loads(spirit_result.stdout)
assert spirit_artifact["request"]["from_address"] == "john@spiritcreekgardens.com"
assert spirit_artifact["audit_record"]["from_address"] == "john@spiritcreekgardens.com"
assert "Email: john@spiritcreekgardens.com" in spirit_artifact["body"]

system = sample_request()
system.pop("identity_hint")
system["system_generated"] = True
system_result = run_cli(["--pretty"], system)
assert system_result.returncode == 0, system_result.stderr
system_artifact = json.loads(system_result.stdout)
assert system_artifact["request"]["from_address"] == "noreply@ww.cx"
assert system_artifact["request"]["reply_to"] is None
assert system_artifact["sender_selection"]["reason"] == "system_generated"
assert "Email: noreply@ww.cx" in system_artifact["body"]

invalid_hint = sample_request()
invalid_hint["identity_hint"] = "unknown-profile"
invalid_hint_result = run_cli([], invalid_hint)
assert invalid_hint_result.returncode == 2
assert "identity_hint is invalid" in invalid_hint_result.stderr

unknown_recipient = sample_request()
unknown_recipient.pop("identity_hint")
unknown_recipient["original_recipient"] = "unknown@ww.cx"
unknown_recipient_result = run_cli([], unknown_recipient)
assert unknown_recipient_result.returncode == 2
assert "original recipient is not a registered mail identity" in unknown_recipient_result.stderr

commercial = sample_request()
commercial["message_class"] = "commercial"
commercial_result = run_cli([], commercial)
assert commercial_result.returncode == 2
assert "unsubscribe_url" in commercial_result.stderr

print("Identity-aware outbound mail preparation CLI validation passed")
print("Canonical sender selection is active; live delivery remains unavailable")
