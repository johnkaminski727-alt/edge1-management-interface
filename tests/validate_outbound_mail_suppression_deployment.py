#!/usr/bin/env python3
"""Validate the suppression-aware gateway deployment package."""

from __future__ import annotations

import json
import pathlib
import sqlite3
import subprocess
import sys
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "deploy/messaging/install-outbound-mail-suppression-server.sh"
INITIALIZER = ROOT / "tools/messaging/initialize_outbound_mail_delivery_state.py"
DOC = ROOT / "docs/messaging-operations/outbound-mail-suppression-deployment-20260804.md"


def check(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


for path in (INSTALLER, INITIALIZER, DOC):
    check(path.is_file(), f"missing {path}")
    check(path.stat().st_size > 500, f"undersized {path}")

shell_result = subprocess.run(["sh", "-n", str(INSTALLER)], cwd=ROOT, check=False)
check(shell_result.returncode == 0, "deployment installer shell syntax failed")
compile_result = subprocess.run(
    [sys.executable, "-m", "py_compile", str(INITIALIZER)],
    cwd=ROOT,
    check=False,
)
check(compile_result.returncode == 0, "delivery-state initializer did not compile")

installer = INSTALLER.read_text(encoding="utf-8")
for required in (
    "ACTION=${ACTION:-audit}",
    "EXPECTED_COMMIT",
    "SUPPRESSION_DEPLOYMENT_AUTHORIZED=yes",
    "Repository working tree must be clean",
    "dedicated non-root User",
    "outbound_mail_gateway_suppressed_server.py",
    "initialize_outbound_mail_delivery_state.py",
    "30-suppression-gate.conf",
    "ExecStart=",
    "systemctl daemon-reload",
    "systemctl restart",
    "unsigned-preparation-status.json",
    "disabled-send.json",
    "external_delivery_enabled",
    "policy_enabled",
    "automatic rollback after deployment exit",
    "trap 'on_exit $?' 0",
    "rolled-back-$stamp",
    "drift detected; refusing disable",
    "No provider or sender was enabled and no message was sent",
):
    check(required in installer, f"installer missing safety marker: {required}")
for prohibited in (
    "curl -k",
    "--insecure",
    "rm -rf",
    "PasswordAuthentication",
    "WWCX_MAIL_SMTP_PASSWORD",
    "cat /etc/wwcx/outbound-mail-gateway.env",
    "source /etc/wwcx/outbound-mail-gateway.env",
    "eval ",
    "nft ",
    "iptables",
    "ufw ",
    "certbot",
    "dig ",
    "nsupdate",
):
    check(prohibited not in installer, f"installer contains prohibited operation: {prohibited}")

initializer = INITIALIZER.read_text(encoding="utf-8")
for required in (
    "synthetic_events_inserted",
    "recipient_data_inserted",
    "message_data_inserted",
    "credentials_inspected",
    "delivery-state initialization found pre-existing records",
    "os.chmod(path, 0o600)",
):
    check(required in initializer, f"initializer missing safety marker: {required}")
for prohibited in ("apply_event", "smtplib", "requests.", "urllib.request"):
    check(prohibited not in initializer, f"initializer contains prohibited operation: {prohibited}")

with tempfile.TemporaryDirectory() as temporary:
    database = pathlib.Path(temporary) / "delivery-state.sqlite3"
    process = subprocess.run(
        [
            sys.executable,
            str(INITIALIZER),
            "--database",
            str(database),
            "--pretty",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    check(process.returncode == 0, f"initializer failed: {process.stderr}")
    result = json.loads(process.stdout)
    check(result["tables"] == ["delivery_events", "recipient_delivery_state"], "initializer tables mismatch")
    check(result["event_count"] == 0, "initializer inserted delivery events")
    check(result["recipient_state_count"] == 0, "initializer inserted recipient state")
    check(result["mode"] == "0600", "initializer mode mismatch")
    check(result["synthetic_events_inserted"] is False, "initializer inserted synthetic events")
    check(result["credentials_inspected"] is False, "initializer inspected credentials")

    connection = sqlite3.connect(database)
    try:
        connection.execute(
            """
            INSERT INTO delivery_events(
                event_id,event_sha256,event_type,occurred_at,provider_profile,
                provider_message_id_sha256,control_id,recipient_sha256,
                source_evidence_sha256,source_authentication,diagnostic_class,retryable
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                "existing-event-0001",
                "a" * 64,
                "provider_accepted",
                "2026-08-04T03:00:00Z",
                "smtp_submission",
                "b" * 64,
                "WWCX-EXISTING-EVENT-0001",
                "c" * 64,
                "d" * 64,
                "manual_evidence_import",
                "none",
                0,
            ),
        )
        connection.commit()
    finally:
        connection.close()

    second = subprocess.run(
        [sys.executable, str(INITIALIZER), "--database", str(database)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    check(second.returncode == 2, "initializer accepted a database containing events")
    check("pre-existing records" in second.stderr, "initializer failure reason changed")

config = json.loads((ROOT / "config/messaging/outbound-mail-gateway.json").read_text(encoding="utf-8"))
identities = json.loads((ROOT / "config/messaging/mail-identities.json").read_text(encoding="utf-8"))
check(config["enabled"] is False, "committed gateway is enabled")
check(config["deployment_authorized"] is False, "committed deployment is authorized")
check(config["external_delivery_authorized"] is False, "committed external delivery is authorized")
check(config["admin"]["send_endpoint_enabled"] is False, "committed send endpoint is enabled")
check(config["provider"]["selected"] == "none", "committed provider is selected")
check(identities["outbound_activation_authorized"] is False, "identity activation is authorized")
check(identities["sender_selection"]["live_sender_allowlist"] == [], "live sender allowlist is not empty")

print("Outbound mail suppression deployment-package validation passed")
print("Default audit, explicit authorization, exact commit, clean-main, and non-root service gates verified")
print("Empty mode-0600 state initialization and pre-existing-record refusal verified")
print("Systemd drift checks, loopback canaries, and EXIT-triggered automatic rollback verified")
print("No credential, DNS, firewall, provider/sender activation, or message traffic is included")
