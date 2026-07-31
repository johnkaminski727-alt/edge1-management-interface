#!/usr/bin/env bash
set -Eeuo pipefail
umask 022

APPLY=0
EXPECTED_HOST="edge1.ww.cx"
SOURCE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TARGET="/opt/wwcx-alerting-lab"
while (($#)); do
    case "$1" in
        --apply) APPLY=1; shift ;;
        --expected-host) EXPECTED_HOST="${2:?missing hostname}"; shift 2 ;;
        --source-root) SOURCE_ROOT="$(realpath "${2:?missing source root}")"; shift 2 ;;
        -h|--help)
            echo "Usage: sudo $0 [--expected-host HOST] [--source-root PATH] [--apply]"
            echo "Stages offline probes only; no service, listener, feed, dialplan, or call route is created."
            exit 0
            ;;
        *) echo "Unknown argument: $1" >&2; exit 2 ;;
    esac
done

[[ $EUID -eq 0 ]] || { echo "ERROR run with sudo" >&2; exit 2; }
[[ "$(hostname -f)" == "$EXPECTED_HOST" ]] || { echo "ERROR host mismatch" >&2; exit 2; }

required=(
    tools/alerting/capcp_probe.py
    tools/alerting/capcp_lifecycle_probe.py
    tools/alerting/ebs_tone_probe.py
    tools/alerting/asterisk_alerting_readiness.sh
    tests/fixtures/alerting/capcp-test-alert.xml
    config/alerting/wwcx-alerting-lab-policy.json
)
for relative in "${required[@]}"; do
    [[ -f "$SOURCE_ROOT/$relative" ]] || { echo "ERROR missing $relative" >&2; exit 3; }
done

python3 -m py_compile \
    "$SOURCE_ROOT/tools/alerting/capcp_probe.py" \
    "$SOURCE_ROOT/tools/alerting/capcp_lifecycle_probe.py" \
    "$SOURCE_ROOT/tools/alerting/ebs_tone_probe.py"
bash -n "$SOURCE_ROOT/tools/alerting/asterisk_alerting_readiness.sh"

echo "Validated source: $SOURCE_ROOT"
echo "Target: $TARGET"
echo "No Asterisk, Kamailio, firewall, DNS, certificate, endpoint, route, or listener change is included."
if [[ $APPLY -ne 1 ]]; then
    echo "DRY RUN COMPLETE: rerun with --apply to install the offline laboratory tools."
    exit 0
fi

TS="$(date -u +%Y%m%dT%H%M%SZ)"
EVID="/var/lib/wwcx-deployment-evidence/alerting-lab-install/$TS"
mkdir -p "$EVID"
if [[ -d "$TARGET" ]]; then
    tar -C / -czf "$EVID/previous-wwcx-alerting-lab.tgz" "${TARGET#/}"
fi

install -d -o root -g root -m 0755 "$TARGET/bin" "$TARGET/fixtures" "$TARGET/policy"
install -o root -g root -m 0755 "$SOURCE_ROOT/tools/alerting/capcp_probe.py" "$TARGET/bin/"
install -o root -g root -m 0755 "$SOURCE_ROOT/tools/alerting/capcp_lifecycle_probe.py" "$TARGET/bin/"
install -o root -g root -m 0755 "$SOURCE_ROOT/tools/alerting/ebs_tone_probe.py" "$TARGET/bin/"
install -o root -g root -m 0755 "$SOURCE_ROOT/tools/alerting/asterisk_alerting_readiness.sh" "$TARGET/bin/"
install -o root -g root -m 0644 "$SOURCE_ROOT/tests/fixtures/alerting/capcp-test-alert.xml" "$TARGET/fixtures/"
install -o root -g root -m 0644 "$SOURCE_ROOT/config/alerting/wwcx-alerting-lab-policy.json" "$TARGET/policy/"

find "$TARGET" -type f -print0 | sort -z | xargs -0 sha256sum >"$EVID/installed-sha256.txt"
"$TARGET/bin/capcp_probe.py" "$TARGET/fixtures/capcp-test-alert.xml" >"$EVID/capcp-smoke.json"
"$TARGET/bin/capcp_lifecycle_probe.py" "$TARGET/fixtures/capcp-test-alert.xml" >"$EVID/lifecycle-smoke.json"
"$TARGET/bin/asterisk_alerting_readiness.sh" --expected-host "$EXPECTED_HOST" >"$EVID/asterisk-readiness.txt" || true

echo "ALERTING LAB INSTALLED"
echo "Evidence directory: $EVID"
echo "No network feed or transmission path was activated."
