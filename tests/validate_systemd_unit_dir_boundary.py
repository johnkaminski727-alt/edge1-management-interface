#!/usr/bin/env python3
"""Static safety checks for the Edge1 systemd unit-directory trust boundary."""

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = (ROOT / "deploy" / "install-time-authority-edge1.sh").read_text(encoding="utf-8")
PREFLIGHT = (ROOT / "deploy" / "time-authority-edge1-preflight.sh").read_text(encoding="utf-8")
REPAIR = (ROOT / "deploy" / "repair-edge1-systemd-unit-dir-boundary.sh").read_text(encoding="utf-8")

# The regression was caused by applying Time Authority service ownership to both
# the application data directory and the global systemd unit directory.
unsafe_joined_install = 'install -d -m 0750 -o "$SERVICE_USER" -g "$SERVICE_USER" "$DATA_DIR" "$UNIT_DIR"'
if unsafe_joined_install in INSTALLER:
    raise SystemExit("Time Authority installer still grants service-user ownership of the systemd unit directory")

required_installer = (
    'install -d -m 0750 -o "$SERVICE_USER" -g "$SERVICE_USER" "$DATA_DIR"',
    'UNIT_DIR_OWNER=$(stat -c \'%U:%G\' "$UNIT_DIR"',
    'UNIT_DIR_MODE=$(stat -c \'%a\' "$UNIT_DIR"',
    'systemd unit directory must remain root:root mode 755',
)
for token in required_installer:
    if token not in INSTALLER:
        raise SystemExit(f"missing installer systemd-boundary guard: {token}")

required_preflight = (
    'UNIT_DIR=${EDGE1_TIME_AUTHORITY_UNIT_DIR:-/etc/systemd/system}',
    'UNIT_DIR_OWNER=$(stat -c \'%U:%G\' "$UNIT_DIR"',
    'UNIT_DIR_MODE=$(stat -c \'%a\' "$UNIT_DIR"',
    'systemd unit directory must remain root:root mode 755',
)
for token in required_preflight:
    if token not in PREFLIGHT:
        raise SystemExit(f"missing preflight systemd-boundary guard: {token}")

required_repair = (
    'TARGET=${EDGE1_SYSTEMD_UNIT_DIR:-/etc/systemd/system}',
    'EXPECTED_BAD_OWNER=${EDGE1_EXPECTED_BAD_UNIT_DIR_OWNER:-bigbird-time:bigbird-time}',
    'EXPECTED_BAD_MODE=${EDGE1_EXPECTED_BAD_UNIT_DIR_MODE:-750}',
    'DESIRED_OWNER=root:root',
    'DESIRED_MODE=755',
    'Run with --apply only after explicit production security-change approval.',
    'chown "$DESIRED_OWNER" "$TARGET"',
    'chmod "$DESIRED_MODE" "$TARGET"',
    'service_state_changed=false',
    'unit_contents_changed=false',
)
for token in required_repair:
    if token not in REPAIR:
        raise SystemExit(f"missing remediation safety behavior: {token}")

# The remediation is allowed to inspect systemd state, but it must not mutate
# service lifecycle or daemon state. The only live mutation is target directory
# owner/mode after the exact-state guard and explicit --apply.
for pattern in (
    r"\bsystemctl\s+(start|stop|restart|reload|enable|disable|mask|unmask|daemon-reload)\b",
    r"\bservice\s+\S+\s+(start|stop|restart|reload)\b",
    r"\bnft\s+(add|delete|insert|replace|flush)\b",
    r"\biptables\b",
    r"\bufw\b",
):
    if re.search(pattern, REPAIR, re.IGNORECASE):
        raise SystemExit(f"prohibited remediation behavior present: {pattern}")

print("systemd unit-directory boundary validation passed")
