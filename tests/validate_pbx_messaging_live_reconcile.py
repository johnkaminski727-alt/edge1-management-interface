#!/usr/bin/env python3
"""Static safety validation for PBX/Messaging live observability reconciliation."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APPLY = ROOT / "deploy" / "communications" / "apply-pbx-messaging-observability.sh"
CAPTURE = ROOT / "tools" / "communications" / "capture-pbx-messaging-runtime.sh"
apply = APPLY.read_text(encoding="utf-8")
capture = CAPTURE.read_text(encoding="utf-8")

required_apply = (
    "WWCX-PBX-MESSAGING-OBSERVABILITY-001",
    "--expected-commit",
    'HEAD=$(git -C "$REPO_ROOT" rev-parse HEAD)',
    'systemctl restart "$TELEPHONY_SERVICE"',
    'ASTERISK_PID_BEFORE=',
    'ASTERISK_PID_AFTER=',
    'MESSAGING_PID_BEFORE=',
    'MESSAGING_PID_AFTER=',
    '[ "$ASTERISK_PID_AFTER" = "$ASTERISK_PID_BEFORE" ]',
    '[ "$MESSAGING_PID_AFTER" = "$MESSAGING_PID_BEFORE" ]',
    "rollback_performed=true",
    "rollback_performed=false",
    "trunks_total",
    "trunks_healthy",
    "trunks_planned",
    'planned[0]["status"] == "planned"',
    "telephony-listener-before.txt",
    "telephony-listener-after.txt",
    "127\\.0\\.0\\.1:8096",
    "messaging-observability.json",
    "capture-pbx-messaging-runtime.sh",
    "Call/SMS/MMS traffic generated: no",
)
for marker in required_apply:
    if marker not in apply:
        raise SystemExit(f"live reconciliation missing required marker: {marker}")

# Exactly the read-only Telephony Console may be restarted by this wrapper.
for prohibited in (
    'systemctl restart "$ASTERISK_SERVICE"',
    'systemctl restart "$MESSAGING_SERVICE"',
    "systemctl reload",
    "systemctl stop",
    "systemctl enable",
    "systemctl disable",
    "channel originate",
    "dialplan reload",
    "pjsip send register",
    "send_sms",
    "send_mms",
    "release_quarantine",
    "nft add",
    "iptables -",
    "ufw allow",
    "curl -X POST",
    "curl --request POST",
):
    if prohibited in apply:
        raise SystemExit(f"live reconciliation contains prohibited action: {prohibited}")

if "awk '$5 ~ /:8096$/" in apply:
    raise SystemExit("live reconciliation still reads the ss peer-address column")
if "awk '$4 ~ /:8096$/" not in apply:
    raise SystemExit("live reconciliation does not inspect the ss local-listener column")
if "awk '$5 ~ /:(5060|5061|5038|58080|8088|8089)$/" in capture:
    raise SystemExit("runtime capture still reads the ss peer-address column")
if "awk '$4 ~ /:(5060|5061|5038|58080|8088|8089)$/" not in capture:
    raise SystemExit("runtime capture does not inspect the ss local-listener column")

print("PBX + Messaging live reconciliation validation passed")
print("Only the read-only Telephony Console may restart; Asterisk and Messaging PIDs must remain unchanged")
