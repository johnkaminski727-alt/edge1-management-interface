#!/bin/sh
set -eu
umask 077

ACTION=${ACTION:-audit}
REPO=${REPO:-/opt/edge1-management-interface}
SERVICE=${SERVICE:-wwcx-outbound-mail-gateway.service}
EXPECTED_HOST=${EXPECTED_HOST:-edge1.ww.cx}
EXPECTED_COMMIT=${EXPECTED_COMMIT:-}
SUPPRESSION_DEPLOYMENT_AUTHORIZED=${SUPPRESSION_DEPLOYMENT_AUTHORIZED:-no}
STATE_DIR=${STATE_DIR:-/var/lib/wwcx-outbound-mail}
SUPPRESSION_DATABASE=${SUPPRESSION_DATABASE:-$STATE_DIR/delivery-state.sqlite3}
RUNTIME_CONFIG=${RUNTIME_CONFIG:-/etc/wwcx/outbound-mail-gateway.json}
IDENTITIES=${IDENTITIES:-$REPO/config/messaging/mail-identities.json}
DROPIN_DIR=${DROPIN_DIR:-/etc/systemd/system/$SERVICE.d}
DROPIN=${DROPIN:-$DROPIN_DIR/30-suppression-gate.conf}
EVIDENCE_ROOT=${EVIDENCE_ROOT:-/var/lib/wwcx-deployment-evidence/outbound-mail-suppression-server}
LISTEN_HOST=${LISTEN_HOST:-127.0.0.1}
LISTEN_PORT=${LISTEN_PORT:-8104}

case "$ACTION" in
    audit|install|verify|disable) ;;
    *) echo "ACTION must be audit, install, verify, or disable." >&2; exit 2 ;;
esac

for path_value in "$REPO" "$STATE_DIR" "$SUPPRESSION_DATABASE" "$RUNTIME_CONFIG" "$IDENTITIES" "$DROPIN_DIR" "$DROPIN" "$EVIDENCE_ROOT"; do
    case "$path_value" in
        *" "*|*"	"*) echo "Configured paths must not contain whitespace." >&2; exit 1 ;;
    esac
done

if [ "$(id -u)" -ne 0 ]; then
    echo "This deployment package must run as root." >&2
    exit 1
fi
host=$(hostname -f 2>/dev/null || hostname)
if [ "$host" != "$EXPECTED_HOST" ]; then
    echo "Host mismatch: expected $EXPECTED_HOST but found $host" >&2
    exit 1
fi

cd "$REPO"
branch=$(git branch --show-current)
head_commit=$(git rev-parse HEAD)
status=$(git status --porcelain --untracked-files=all)
[ "$branch" = main ] || { echo "Repository branch must be main." >&2; exit 1; }
if [ -n "$status" ]; then
    echo "Repository working tree must be clean." >&2
    git status --short >&2
    exit 1
fi
if [ -z "$EXPECTED_COMMIT" ] || [ "$head_commit" != "$EXPECTED_COMMIT" ]; then
    echo "Repository HEAD does not match explicit EXPECTED_COMMIT." >&2
    exit 1
fi

for required in \
    server/outbound_mail_gateway_suppressed_server.py \
    server/outbound_mail_suppression_gate.py \
    server/outbound_mail_delivery_events.py \
    tools/messaging/initialize_outbound_mail_delivery_state.py \
    tests/validate_outbound_mail_suppression_gate.py \
    tests/validate_outbound_mail_suppression_server.py
 do
    [ -f "$required" ] || { echo "Required repository file is absent: $required" >&2; exit 1; }
 done
[ -f "$RUNTIME_CONFIG" ] || { echo "Runtime gateway configuration is absent." >&2; exit 1; }
[ -f "$IDENTITIES" ] || { echo "Identity registry is absent." >&2; exit 1; }

service_user=$(systemctl show "$SERVICE" -p User --value)
service_group=$(systemctl show "$SERVICE" -p Group --value)
if [ -z "$service_user" ] || [ "$service_user" = root ]; then
    echo "Gateway service must use a dedicated non-root User." >&2
    exit 1
fi
[ -n "$service_group" ] || service_group=$service_user
id "$service_user" >/dev/null 2>&1 || { echo "Gateway service user does not exist." >&2; exit 1; }

stamp=$(date -u +%Y%m%dT%H%M%SZ)
evidence_dir=$EVIDENCE_ROOT/$stamp
install -d -m 0700 "$evidence_dir"
summary=$evidence_dir/summary.txt
failures=$evidence_dir/failures.txt
: > "$summary"
: > "$failures"
record() { printf '%s=%s\n' "$1" "$2" | tee -a "$summary"; }
manifest() {
    (
        cd "$evidence_dir"
        find . -maxdepth 1 -type f ! -name SHA256SUMS -print | sort | xargs sha256sum > SHA256SUMS
    )
}

record captured_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
record host "$host"
record principal "$(id -un)"
record action "$ACTION"
record repository "$REPO"
record branch "$branch"
record head_commit "$head_commit"
record service "$SERVICE"
record service_user "$service_user"
record service_group "$service_group"
record runtime_config "$RUNTIME_CONFIG"
record suppression_database "$SUPPRESSION_DATABASE"
record dropin "$DROPIN"
record provider_credentials_read no
record provider_or_sender_enabled no
record external_delivery_enabled no
record message_prepared no
record message_sent no
record dns_modified no
record firewall_modified no
record public_listener_added no

systemctl show "$SERVICE" -p ActiveState -p SubState -p UnitFileState -p User -p Group -p ExecStart > "$evidence_dir/service-before.txt"
ss -ltnp > "$evidence_dir/listeners-before.txt" 2>&1 || true
systemctl cat "$SERVICE" > "$evidence_dir/unit-before.txt"
sha256sum \
    server/outbound_mail_gateway_suppressed_server.py \
    server/outbound_mail_suppression_gate.py \
    server/outbound_mail_delivery_events.py \
    tools/messaging/initialize_outbound_mail_delivery_state.py \
    "$RUNTIME_CONFIG" "$IDENTITIES" > "$evidence_dir/source-sha256.txt"

python3 - "$RUNTIME_CONFIG" "$IDENTITIES" <<'PY' > "$evidence_dir/safe-state.json"
import json
import sys
config = json.load(open(sys.argv[1], encoding="utf-8"))
identities = json.load(open(sys.argv[2], encoding="utf-8"))
checks = {
    "gateway_enabled": config.get("enabled") is True,
    "deployment_authorized": config.get("deployment_authorized") is True,
    "external_delivery_authorized": config.get("external_delivery_authorized") is True,
    "send_endpoint_enabled": config.get("admin", {}).get("send_endpoint_enabled") is True,
    "selected_provider": config.get("provider", {}).get("selected"),
    "live_sender_count": len(identities.get("sender_selection", {}).get("live_sender_allowlist", [])),
    "identity_activation_authorized": identities.get("outbound_activation_authorized") is True,
}
unsafe = any([
    checks["gateway_enabled"], checks["deployment_authorized"],
    checks["external_delivery_authorized"], checks["send_endpoint_enabled"],
    checks["identity_activation_authorized"], checks["live_sender_count"] > 0,
    checks["selected_provider"] not in {None, "none"},
])
print(json.dumps({"safe_disabled": not unsafe, "checks": checks}, indent=2, sort_keys=True))
if unsafe:
    raise SystemExit(1)
PY

python3 -m py_compile \
    server/outbound_mail_gateway_suppressed_server.py \
    server/outbound_mail_suppression_gate.py \
    server/outbound_mail_delivery_events.py \
    tools/messaging/initialize_outbound_mail_delivery_state.py
python3 tests/validate_outbound_mail_suppression_gate.py > "$evidence_dir/suppression-gate-validation.txt"
python3 tests/validate_outbound_mail_suppression_server.py > "$evidence_dir/suppression-server-validation.txt" 2>&1

systemctl is-active --quiet "$SERVICE" || { echo "Gateway service is not active before action." >&2; exit 1; }
if ss -ltnH | awk -v port=":$LISTEN_PORT" '$4 ~ port "$" {print $4}' | grep -Ev '^(127\.0\.0\.1|\[::1\]):' >/dev/null 2>&1; then
    echo "An external listener exists on the gateway port." >&2
    exit 1
fi

write_dropin() {
    target=$1
    cat > "$target" <<EOF
[Service]
ExecStart=
ExecStart=/usr/bin/python3 $REPO/server/outbound_mail_gateway_suppressed_server.py --config $RUNTIME_CONFIG --identities $IDENTITIES --host $LISTEN_HOST --port $LISTEN_PORT --suppression-database $SUPPRESSION_DATABASE
EOF
}

verify_live() {
    systemctl is-active --quiet "$SERVICE" || return 1
    exec_start=$(systemctl show "$SERVICE" -p ExecStart --value)
    printf '%s\n' "$exec_start" > "$evidence_dir/execstart-after.txt"
    printf '%s' "$exec_start" | grep -F outbound_mail_gateway_suppressed_server.py >/dev/null || return 1
    [ -f "$SUPPRESSION_DATABASE" ] || return 1
    [ "$(stat -c '%a' "$SUPPRESSION_DATABASE")" = 600 ] || return 1
    [ "$(stat -c '%U' "$SUPPRESSION_DATABASE")" = "$service_user" ] || return 1
    [ "$(stat -c '%G' "$SUPPRESSION_DATABASE")" = "$service_group" ] || return 1
    health_code=$(curl --silent --show-error --max-time 8 --output "$evidence_dir/health.json" --write-out '%{http_code}' "http://$LISTEN_HOST:$LISTEN_PORT/outbound-mail/healthz")
    [ "$health_code" = 200 ] || return 1
    status_code=$(curl --silent --show-error --max-time 8 --output "$evidence_dir/status.json" --write-out '%{http_code}' "http://$LISTEN_HOST:$LISTEN_PORT/outbound-mail/status")
    [ "$status_code" = 200 ] || return 1
    prepare_code=$(curl --silent --show-error --max-time 8 --output "$evidence_dir/unsigned-preparation-status.json" --write-out '%{http_code}' "http://$LISTEN_HOST:$LISTEN_PORT/outbound-mail/api/v1/status")
    [ "$prepare_code" = 401 ] || return 1
    send_code=$(curl --silent --show-error --max-time 8 \
        --header 'Content-Type: application/json' \
        --data '{"to":["suppression-canary.invalid@example.invalid"],"subject":"Disabled suppression canary","body":"This request must fail before provider submission.","message_class":"business_correspondence","confirm_send":true}' \
        --output "$evidence_dir/disabled-send.json" --write-out '%{http_code}' \
        "http://$LISTEN_HOST:$LISTEN_PORT/outbound-mail/send")
    [ "$send_code" = 403 ] || return 1
    python3 - "$evidence_dir/status.json" "$evidence_dir/disabled-send.json" <<'PY'
import json
import sys
status = json.load(open(sys.argv[1], encoding="utf-8"))
send = json.load(open(sys.argv[2], encoding="utf-8"))
assert status.get("external_delivery_enabled") is False
assert status.get("policy_enabled") is False
assert not any(item.get("ready") for item in status.get("providers", []))
assert send.get("error") == "delivery_disabled"
PY
    if ss -ltnH | awk -v port=":$LISTEN_PORT" '$4 ~ port "$" {print $4}' | grep -Ev '^(127\.0\.0\.1|\[::1\]):' >/dev/null 2>&1; then
        return 1
    fi
}

if [ "$ACTION" = audit ]; then
    current_exec=$(systemctl show "$SERVICE" -p ExecStart --value)
    case "$current_exec" in
        *outbound_mail_gateway_suppressed_server.py*) state=installed ;;
        *outbound_mail_gateway_server.py*) state=not_installed ;;
        *) state=unknown_entrypoint ;;
    esac
    record readiness_state "$state"
    record failures 0
    manifest
    echo "Suppression-server audit completed: $evidence_dir"
    exit 0
fi

if [ "$ACTION" = verify ]; then
    if ! verify_live; then
        record readiness_state verification_failed
        record failures 1
        manifest
        exit 1
    fi
    record readiness_state suppression_server_active_safe_disabled
    record failures 0
    manifest
    echo "Suppression-server verification completed: $evidence_dir"
    exit 0
fi

[ "$SUPPRESSION_DEPLOYMENT_AUTHORIZED" = yes ] || { echo "Install or disable requires SUPPRESSION_DEPLOYMENT_AUTHORIZED=yes." >&2; exit 1; }

backup_dropin=$evidence_dir/30-suppression-gate.conf.before
had_dropin=no
if [ -e "$DROPIN" ]; then
    [ -f "$DROPIN" ] && [ ! -L "$DROPIN" ] || { echo "Existing suppression drop-in is unsafe." >&2; exit 1; }
    cp -a "$DROPIN" "$backup_dropin"
    had_dropin=yes
fi
record existing_dropin "$had_dropin"

db_created=no
mutated=no
completed=no
rollback() {
    reason=$1
    trap - 0 HUP INT TERM
    set +e
    if [ "$mutated" = yes ]; then
        if [ "$had_dropin" = yes ]; then
            install -D -o root -g root -m 0644 "$backup_dropin" "$DROPIN"
        else
            rm -f "$DROPIN"
        fi
        systemctl daemon-reload
        systemctl restart "$SERVICE"
        if [ "$db_created" = yes ] && [ -f "$SUPPRESSION_DATABASE" ]; then
            mv "$SUPPRESSION_DATABASE" "$SUPPRESSION_DATABASE.rolled-back-$stamp"
        fi
    fi
    printf '%s\n' "$reason" >> "$failures"
    record rollback_executed yes
    record rollback_reason "$reason"
    systemctl show "$SERVICE" -p ActiveState -p SubState -p ExecStart > "$evidence_dir/service-after-rollback.txt" 2>&1
    manifest
    exit 1
}
on_exit() {
    rc=$1
    trap - 0 HUP INT TERM
    if [ "$rc" -ne 0 ] && [ "$mutated" = yes ] && [ "$completed" != yes ]; then
        rollback "automatic rollback after deployment exit $rc"
    fi
    exit "$rc"
}
trap 'on_exit $?' 0
trap 'exit 130' HUP INT TERM

if [ "$ACTION" = disable ]; then
    [ -f "$DROPIN" ] && [ ! -L "$DROPIN" ] || { echo "Suppression drop-in is absent or unsafe." >&2; exit 1; }
    expected_dropin=$evidence_dir/expected-dropin.conf
    write_dropin "$expected_dropin"
    cmp -s "$expected_dropin" "$DROPIN" || { echo "Suppression drop-in drift detected; refusing disable." >&2; exit 1; }
    mv "$DROPIN" "$evidence_dir/30-suppression-gate.conf.disabled"
    mutated=yes
    systemctl daemon-reload
    systemctl restart "$SERVICE"
    sleep 2
    systemctl is-active --quiet "$SERVICE" || rollback "base gateway did not recover after disable"
    exec_start=$(systemctl show "$SERVICE" -p ExecStart --value)
    printf '%s' "$exec_start" | grep -F outbound_mail_gateway_server.py >/dev/null || rollback "base gateway entrypoint was not restored"
    record readiness_state suppression_server_disabled_database_preserved
    record rollback_executed no
    record failures 0
    systemctl show "$SERVICE" -p ActiveState -p SubState -p ExecStart > "$evidence_dir/service-after.txt"
    manifest
    completed=yes
    trap - 0 HUP INT TERM
    echo "Suppression-server disable completed: $evidence_dir"
    exit 0
fi

[ ! -e "$SUPPRESSION_DATABASE" ] || { echo "Suppression database already exists; use verify or review existing state." >&2; exit 1; }
install -d -o "$service_user" -g "$service_group" -m 0750 "$STATE_DIR"
temp_db=$STATE_DIR/.delivery-state.sqlite3.$stamp.tmp
python3 tools/messaging/initialize_outbound_mail_delivery_state.py --database "$temp_db" --pretty > "$evidence_dir/database-initialization.json"
chown "$service_user:$service_group" "$temp_db"
chmod 0600 "$temp_db"
mv "$temp_db" "$SUPPRESSION_DATABASE"
db_created=yes
mutated=yes

install -d -o root -g root -m 0755 "$DROPIN_DIR"
temp_dropin=$evidence_dir/30-suppression-gate.conf.proposed
write_dropin "$temp_dropin"
install -o root -g root -m 0644 "$temp_dropin" "$DROPIN"
systemctl daemon-reload
systemctl restart "$SERVICE"
sleep 2
verify_live || rollback "suppression-aware gateway post-install verification failed"

systemctl show "$SERVICE" -p ActiveState -p SubState -p UnitFileState -p User -p Group -p ExecStart > "$evidence_dir/service-after.txt"
ss -ltnp > "$evidence_dir/listeners-after.txt" 2>&1 || true
systemctl cat "$SERVICE" > "$evidence_dir/unit-after.txt"
journalctl -u "$SERVICE" --since=-5min --no-pager -n 200 > "$evidence_dir/journal-after.txt" 2>&1 || true
record readiness_state suppression_server_active_safe_disabled
record rollback_executed no
record failures 0
manifest
completed=yes
trap - 0 HUP INT TERM
printf '%s\n' "Suppression-aware outbound-mail server installation completed."
printf '%s\n' "No provider or sender was enabled and no message was sent."
printf 'Evidence: %s\n' "$evidence_dir"
