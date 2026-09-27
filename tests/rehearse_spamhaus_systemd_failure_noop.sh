#!/usr/bin/env bash
# Assignment 249 — OPTIONAL harmless systemd failure-injection rehearsal.
# Exercises a uniquely named transient timer whose service runs ONLY /usr/bin/false.
# Does not touch nftables, install production units, enable restoration or reboot.
set -euo pipefail

BASE="edge1-spamhaus-a249-probe-$$"
TIMER="${BASE}.timer"
SERVICE="${BASE}.service"
ARMED=0

cleanup() {
    # Never stop/reset an unrelated unit if creation failed or name was occupied.
    if [[ "$ARMED" != 1 ]]; then return; fi
    sudo /usr/bin/systemctl stop "$TIMER" "$SERVICE" >/dev/null 2>&1 || true
    sudo /usr/bin/systemctl reset-failed "$TIMER" "$SERVICE" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "=== Assignment 249: isolated failure evidence for harmless transient timer ==="
/usr/bin/test -x /usr/bin/systemd-run
/usr/bin/test -x /usr/bin/systemctl
/usr/bin/test -x /usr/bin/false
/usr/bin/test -x /usr/bin/journalctl

if /usr/bin/systemctl list-units --all --no-legend "$TIMER" | /usr/bin/grep -q .; then
    echo "STOP: unique transient timer name already occupied"
    exit 2
fi
if /usr/bin/systemctl list-units --all --no-legend "$SERVICE" | /usr/bin/grep -q .; then
    echo "STOP: unique transient service name already occupied"
    exit 2
fi

echo "=== Arm a 10-second timer to run ONLY /usr/bin/false ==="
sudo /usr/bin/systemd-run --unit="$BASE" --on-active=10s \
    --timer-property=AccuracySec=1s /usr/bin/false
ARMED=1

state="$(/usr/bin/systemctl show "$TIMER" -p ActiveState --value)"
target="$(/usr/bin/systemctl show "$TIMER" -p Unit --value)"
execstart="$(/usr/bin/systemctl show "$SERVICE" -p ExecStart --value)"
echo "Timer state: $state"
echo "Timer target: $target"
echo "Service executable: $execstart"
if [[ "$state" != active || "$target" != "$SERVICE" || "$execstart" != *"path=/usr/bin/false"* ]]; then
    echo "FAIL: expected harmless transient timer target or command not verified"
    exit 3
fi
echo "PASS: harmless failure timer independently armed"

observed=0
for i in {1..30}; do
    result="$(/usr/bin/systemctl show "$SERVICE" -p Result --value 2>/dev/null || true)"
    stamp="$(/usr/bin/systemctl show "$SERVICE" -p ExecMainStartTimestampMonotonic --value 2>/dev/null || true)"
    status="$(/usr/bin/systemctl show "$SERVICE" -p ExecMainStatus --value 2>/dev/null || true)"
    if [[ "$result" == exit-code && "$stamp" =~ ^[0-9]+$ && "$stamp" -gt 0 && "$status" == 1 ]]; then
        echo "PASS: independent /usr/bin/false execution recorded Result=exit-code and ExecMainStatus=1"
        observed=1
        break
    fi
    /usr/bin/sleep 1
done
if [[ "$observed" != 1 ]]; then
    echo "FAIL: independently scheduled failure was not verified"
    exit 4
fi

echo "=== Root-readable journal evidence for this harmless TEST unit ==="
if sudo /usr/bin/journalctl --no-pager --quiet -u "$SERVICE" -n 25; then
    echo "NOTE: Journal queried as root; inspect preceding output for this exact test unit."
else
    echo "WARNING: Root journal query failed; investigation required"
    exit 5
fi
echo "=== Assignment 249 complete (probe unit cleanup on exit) ==="
