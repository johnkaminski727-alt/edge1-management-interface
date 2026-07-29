#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)"
EVIDENCE_ROOT=${EDGE1_SECURITY_CONTROLS_EVIDENCE_ROOT:-/var/lib/wwcx-deployment-evidence/security-controls-inspection}
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
EVIDENCE_DIR=${1:-$EVIDENCE_ROOT/$STAMP}
OUTPUT="$EVIDENCE_DIR/security-controls.json"

fail() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

[ "$(id -u)" -eq 0 ] || fail "run as root, for example: sudo bash $0"
[ -d "$ROOT/.git" ] || fail "repository not found: $ROOT"
for command in bash git hostname install python3 sha256sum; do
    command -v "$command" >/dev/null 2>&1 || fail "required command is unavailable: $command"
done

HOST=$(hostname -f 2>/dev/null || hostname)
case "$HOST" in
    edge1|edge1.ww.cx) ;;
    *) fail "inspection is restricted to Edge1; observed host: $HOST" ;;
esac

install -d -o root -g root -m 0700 "$EVIDENCE_DIR"
printf '%s\n' "$HOST" > "$EVIDENCE_DIR/host.txt"
printf '%s\n' "$(id -un)" > "$EVIDENCE_DIR/principal.txt"
git -C "$ROOT" rev-parse HEAD > "$EVIDENCE_DIR/revision.txt"
git -C "$ROOT" status --short --branch > "$EVIDENCE_DIR/git-status.txt"
cat > "$EVIDENCE_DIR/command-plan.txt" <<'PLAN'
Read-only inspection plan:
- query systemd unit properties with systemctl show;
- read nftables ruleset as JSON and retain aggregate object counts only;
- read Fail2ban status and retain jail names and numeric counters only;
- exclude rules, addresses, ports, packet payloads, banned-IP lists, and raw command output;
- make no service, firewall, DNS, routing, IDS, proxy, or Fail2ban changes.
PLAN

bash "$ROOT/tools/security/validate-security-controls-inspection.sh" | tee "$EVIDENCE_DIR/repository-validation.txt"
python3 "$ROOT/tools/security/security_controls_inspector.py" --output "$OUTPUT" | tee "$EVIDENCE_DIR/inspection-summary.txt"

python3 - "$OUTPUT" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
document = json.loads(path.read_text(encoding="utf-8"))
if document.get("read_only") is not True:
    raise SystemExit("read_only must be true")
if document.get("traffic_controls_changed") is not False:
    raise SystemExit("traffic_controls_changed must be false")
privacy = document.get("privacy")
if not isinstance(privacy, dict):
    raise SystemExit("privacy contract is missing")
for key in (
    "raw_rules_included",
    "addresses_included",
    "ports_included",
    "packet_payloads_included",
    "banned_ip_list_included",
    "raw_command_output_included",
):
    if privacy.get(key) is not False:
        raise SystemExit(f"privacy.{key} must be false")
if not isinstance(document.get("firewall"), dict):
    raise SystemExit("firewall summary is missing")
if not isinstance(document.get("fail2ban"), dict):
    raise SystemExit("fail2ban summary is missing")
print(json.dumps({
    "ok": True,
    "firewall_readable": document["firewall"].get("ruleset_readable"),
    "fail2ban_readable": document["fail2ban"].get("status_readable"),
    "traffic_controls_changed": False,
}))
PY

sha256sum "$OUTPUT" > "$EVIDENCE_DIR/sha256.txt"
printf 'completed_at=%s\nread_only=true\ntraffic_controls_changed=false\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$EVIDENCE_DIR/result.txt"

printf 'Security Controls inspection passed.\n'
printf 'Evidence: %s\n' "$EVIDENCE_DIR"
printf 'No firewall, DNS, routing, IDS, proxy, Fail2ban, or service controls were changed.\n'
