#!/usr/bin/env bash
# Assignment 248 — OPTIONAL operator-run, harmless transient systemd timer.
# No nftables commands, reboot, production service installation or enablement.
# Creates one uniquely named transient timer whose ONLY command is /usr/bin/true.
# Run only after explicit operator review. Never use this as rollback proof.
set -euo pipefail

BASE="edge1-spamhaus-a248-probe-$$"
TIMER="${BASE}.timer"
SERVICE="${BASE}.service"
ARMED=0
cleanup() {
    # Do not stop an existing unit if the collision check or arming failed.
    if [[ "$ARMED" != 1 ]]; then return; fi
    sudo /usr/bin/systemctl stop "$TIMER" "$SERVICE" >/dev/null 2>&1 || true
    sudo /usr/bin/systemctl reset-failed "$TIMER" "$SERVICE" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "=== Assignment 248: no-firewall systemd transient timer rehearsal ==="
/usr/bin/test -x /usr/bin/systemd-run || exit 2
/usr/bin/test -x /usr/bin/systemctl || exit 2
/usr/bin/test -x /usr/bin/true || exit 2

# A collision must stop instead of attaching to an existing timer.
if /usr/bin/systemctl list-units --all --no-legend "$TIMER" | /usr/bin/grep -q .; then
    echo "STOP: transient test name occupied"
    exit 2
fi

echo "=== Arm independent timer (only runs /usr/bin/true) ==="
sudo /usr/bin/systemd-run --unit="$BASE" --on-active=15s \
    --timer-property=AccuracySec=1s /usr/bin/true
ARMED=1

state="$(/usr/bin/systemctl show "$TIMER" -p ActiveState --value)"
target="$(/usr/bin/systemctl show "$TIMER" -p Unit --value)"
execstart="$(/usr/bin/systemctl show "$SERVICE" -p ExecStart --value)"
echo "Timer state: $state"
echo "Timer target: $target"
echo "Service command: $execstart"

if [[ "$state" != active || "$target" != "$SERVICE" ]]; then
    echo "STOP: transient timer verification failed"
    exit 3
fi
if [[ "$execstart" != *"path=/usr/bin/true"* ]]; then
    echo "STOP: harmless service executable not verified"
    exit 3
fi
echo "PASS: no-op timer armed with correct service"

# Do not take any destructive action if it never fires.
for i in {1..30}; do
    outcome="$(/usr/bin/systemctl show "$SERVICE" -p Result --value)"
    stamp="$(/usr/bin/systemctl show "$SERVICE" -p ExecMainStartTimestampMonotonic --value)"
    if [[ "$outcome" == success && "$stamp" =~ ^[0-9]+$ && "$stamp" -gt 0 ]]; then
        echo "PASS: independent harmless service fired successfully"
        echo "=== Timer journal (test unit only) ==="
        /usr/bin/journalctl -u "$SERVICE" --no-pager -n 15 || true
        echo "=== Assignment 248 rehearsal complete ==="
        exit 0
    fi
    /usr/bin/sleep 1
done
echo "FAIL: harmless timer did not demonstrate successful firing"
exit 4
