#!/usr/bin/env bash
set -euo pipefail

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)"
cd "$ROOT"

PYTHON_BIN=${PYTHON_BIN:-python3}
TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

printf '%s\n' '== Python syntax =='
"$PYTHON_BIN" -m py_compile tools/security/security_controls_inspector.py

printf '%s\n' '== Targeted tests =='
"$PYTHON_BIN" -m unittest tests.test_security_controls_inspector -v

printf '%s\n' '== Shell syntax =='
bash -n tools/security/inspect-security-controls.sh

printf '%s\n' '== Degraded-environment execution =='
"$PYTHON_BIN" tools/security/security_controls_inspector.py \
  --output "$TMP_DIR/security-controls.json"

"$PYTHON_BIN" - "$TMP_DIR/security-controls.json" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
document = json.loads(path.read_text(encoding='utf-8'))
assert document['read_only'] is True
assert document['traffic_controls_changed'] is False
privacy = document['privacy']
for key in (
    'raw_rules_included',
    'addresses_included',
    'ports_included',
    'packet_payloads_included',
    'banned_ip_list_included',
    'raw_command_output_included',
):
    assert privacy[key] is False
assert isinstance(document['firewall'], dict)
assert isinstance(document['fail2ban'], dict)
PY

printf '%s\n' '== Static mutation boundary =='
! grep -Eiq 'systemctl[[:space:]]+(start|stop|restart|reload|enable|disable)' \
  tools/security/security_controls_inspector.py \
  tools/security/inspect-security-controls.sh
! grep -Eiq 'nft[^[:cntrl:]]+(add|delete|insert|replace|flush)' \
  tools/security/security_controls_inspector.py
! grep -Eiq 'fail2ban-client[^[:cntrl:]]+set' \
  tools/security/security_controls_inspector.py

grep -Fq 'traffic_controls_changed' tools/security/security_controls_inspector.py
grep -Fq 'banned_ip_list_included' tools/security/security_controls_inspector.py
grep -Fq 'raw_command_output_included' tools/security/security_controls_inspector.py

printf '%s\n' 'Security Controls inspection validation passed.'
