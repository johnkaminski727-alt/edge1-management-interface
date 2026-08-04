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
if [ "$branch" != main ]; then
    echo "Repository branch must be main." >&2
    exit 1
fi
if [ -n "$status" ]; then
    echo "Repository working tree must be clean." >&2
    git status --short >&2
    exit 1
fi
if [ -z "$EXPECTED_COMMIT" ] || [ "$head_commit" != "$EXPECTED_COMMIT" ]; then
    echo "Repository HEAD does not match the explicit EXPECTED_COMMIT." >&2
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
    if [ ! -f "$required" ]; then
        echo "Required repository file is absent: $required" >&2
        exit 1
    fi
 done

if [ ! -f "$RUNTIME_CONFIG" ]; then
    echo "Runtime gateway configuration is absent: $RUNTIME_CONFIG" >&2
    exit 1
fi
if [ ! -f "$IDENTITIES" ]; then
    echo "Identity registry is absent: $IDENTITIES" >&2
    exit 1
fi

service_user=$(systemctl show "$SERVICE" -p User --value)
service_group=$(systemctl show "$SERVICE" -p Group --value)
if [ -z "$service_user" ] || [ "$service_user" = root ]; then
    echo "Gateway service must use a dedicated non-root User." >&2
    exit 1
fi
if [ -z "$service_group" ]; then
    service_group=$service_user
fi
if ! id "$service_user" >/dev/null 2>&1; then
    echo "Gateway service user does not exist: $service_user" >&2
    exit 1
fi

stamp=$(date -u +%Y%m%dT%H%M%SZ)
evidence_dir=$EVIDENCE_ROOT/$stamp
install -d -m 0700 "$evidence_dir"
summary=$evidence_dir/summary.txt
failures=$evidence_dir/failures.txt
: > "$summary"
: > "$failures"

record() {
    printf '%s=%s\n' "$1" "$2" | tee -a "$summary"
}
fail() {
    printf '%s\n' "$*" >> "$failures"
    echo "$*" >&2
    return 1
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

systemctl show "$SERVICE" \
    -p ActiveState -p SubState -p UnitFileState -p User -p Group -p ExecStart \
    > "$evidence_dir/service-before.txt"
ss -ltnp > "$evidence_dir/listeners-before.txt" 2>&1 || true
systemctl cat "$SERVICE" > "$evidence_dir/unit-before.txt"
sha256sum \
    server/outbound_mail_gateway_suppressed_server.py \
    server/outbound_mail_suppression_gate.py \
    server/outbound_mail_delivery_events.py \
    tools/messaging/initialize_outbound_mail_delivery_state.py \
    "$RUNTIME_CONFIG" "$IDENTITIES" \
    > "$evidence_dir/source-sha256.txt"

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
    checks["gateway_enabled"],
    checks["deployment_authorized"],
    checks["external_delivery_authorized"],
    checks["send_endpoint_enabled"],
    checks["identity_activation_authorized"],
    checks["live_sender_count"] > 0,
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
python3 tests/validate_outbound_mail_suppression_gate.py \
    > "$evidence_dir/suppression-gate-validation.txt"
python3 tests/validate_outbound_mail_suppression_server.py \
    > "$evidence_dir/suppression-server-validation.txt" 2>&1

if ! systemctl is-active --quiet "$SERVICE"; then
    fail "Gateway service is not active before action."
fi
if ss -ltnH | awk -v port=":$LISTEN_PORT" '$4 ~ port "$" {print $4}' \
    | grep -Ev '^(127\.0\.0\.1|\[::1\]):' >/dev/null 2>&1; then
    fail "An external listener exists on the gateway port."
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
    expected_entrypoint=$1
    systemctl is-active --quiet "$SERVICE" || return 1
    exec_start=$(systemctl show "$SERVICE" -p ExecStart --value)
    printf '%s\n' "$exec_start" > "$evidence_dir/execstart-after.txt"
    printf '%s' "$exec_start" | grep -F "$expected_entrypoint" >/dev/null || return 1
    [ -f "$SUPPRESSION_DATABASE" ] || return 1
    db_mode=$(stat -c '%a' "$SUPPRESSION_DATABASE")
    db_user=$(stat -c '%U' "$SUPPRESSION_DATABASE")
    db_group=$(stat -c '%G' "$SUPPRESSION_DATABASE")
    [ "$db_mode" = 600 ] || return 1
    [ "$db_user" = "$service_user" ] || return 1
    [ "$db_group" = "$service_group" ] || return 1
    health_code=$(curl --silent --show-error --max-time 8 --output "$evidence_dir/health.json" \
        --write-out '%{http_code}' "http://$LISTEN_HOST:$LISTEN_PORT/outbound-mail/healthz")
    [ "$health_code" = 200 ] || return 1
    status_code=$(curl --silent --show-error --max-time 8 --output "$evidence_dir/status.json" \
        --write-out '%{http_code}' "http://$LISTEN_HOST:$LISTEN_PORT/outbound-mail/status")
    [ "$status_code" = 200 ] || return 1
    prepare_code=$(curl --silent --show-error --max-time 8 --output "$evidence_dir/unsigned-preparation-status.json" \
        --write-out '%{http_code}' "http://$LISTEN_HOST:$LISTEN_PORT/outbound-mail/api/v1/status")
    [ "$prepare_code" = 401 ] || return 1
    send_code=$(curl --silent --show-error --max-time 8 \
        --header 'Content-Type: application/json' \
        --data '{"to":["suppression-canary.invalid@example.invalid"],"subject":"Disabled suppression canary","body":"This request must fail before provider submission.","message_class":"business_correspondence","confirm_send":true}' \
        --output "$evidence_dir/disabled-send.json" \
        --write-out '%{http_code}' \
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
    if ss -ltnH | awk -v port=":$LISTEN_PORT" '$4 ~ port "$" {print $4}' \
        | grep -Ev '^(127\.0\.0\.1|\[::1\]):' >/dev/null 2>&1; then
        return 1
    fi
    return 0
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
    (
        cd "$evidence_dir"
        find . -maxdepth 1 -type f ! -name SHA256SUMS -print | sort | xargs sha256sum > SHA256SUMS
    )
    echo "Suppression-server audit completed: $evidence_dir"
    exit 0
fi

if [ "$ACTION" = verify ]; then
    if ! verify_live outbound_mail_gateway_suppressed_server.py; then
        record readiness_state verification_failed
        record failures 1
        exit 1
    fi
    record readiness_state suppression_server_active_safe_disabled
    record failures 0
    (
        cd "$evidence_dir"
        find . -maxdepth 1 -type f ! -name SHA256SUMS -print | sort | xargs sha256sum > SHA256SUMS
    )
    echo "Suppression-server verification completed: $evidence_dir"
    exit 0
fi

if [ "$SUPPRESSION_DEPLOYMENT_AUTHORIZED" != yes ]; then
    echo "Install or disable requires SUPPRESSION_DEPLOYMENT_AUTHORIZED=yes." >&2
    exit 1
fi

backup_dropin=$evidence_dir/30-suppression-gate.conf.before
had_dropin=no
if [ -e "$DROPIN" ]; then
    if [ ! -f "$DROPIN" ] || [ -L "$DROPIN" ]; then
        echo "Existing suppression drop-in is not a regular file." >&2
        exit 1
    fi
    cp -a "$DROPIN" "$backup_dropin"
    had_dropin=yes
fi
record existing_dropin "$had_dropin"

db_created=no
mutated=no
rollback() {
    reason=$1
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
    systemctl show "$SERVICE" -p ActiveState -p SubState -p ExecStart \
        > "$evidence_dir/service-after-rollback.txt" 2>&1
    exit 1
}
trap 'rollback "unexpected deployment failure"' HUP INT TERM

if [ "$ACTION" = disable ]; then
    if [ ! -f "$DROPIN" ] || [ -L "$DROPIN" ]; then
        echo "Suppression drop-in is absent or unsafe; refusing disable." >&2
        exit 1
    fi
    expected_dropin=$evidence_dir/expected-dropin.conf
    write_dropin "$expected_dropin"
    if ! cmp -s "$expected_dropin" "$DROPIN"; then
        echo "Suppression drop-in drift detected; refusing disable." >&2
        exit 1
    fi
    mv "$DROPIN" "$evidence_dir/30-suppression-gate.conf.disabled"
    mutated=yes
    systemctl daemon-reload
    systemctl restart "$SERVICE"
    sleep 2
    if ! systemctl is-active --quiet "$SERVICE"; then
        rollback "base gateway did not recover after disable"
    fi
    exec_start=$(systemctl show "$SERVICE" -p ExecStart --value)
    printf '%s' "$exec_start" | grep -F outbound_mail_gateway_server.py >/dev/null \
        || rollback "base gateway entrypoint was not restored"
    record readiness_state suppression_server_disabled_database_preserved
    record rollback_executed no
    record failures 0
    systemctl show "$SERVICE" -p ActiveState -p SubState -p ExecStart \
        > "$evidence_dir/service-after.txt"
    (
        cd "$evidence_dir"
        find . -maxdepth 1 -type f ! -name SHA256SUMS -print | sort | xargs sha256sum > SHA256SUMS
    )
    trap - HUP INT TERM
    echo "Suppression-server disable completed: $evidence_dir"
    exit 0
fi

if [ -e "$SUPPRESSION_DATABASE" ]; then
    echo "Suppression database already exists; use verify or review existing state." >&2
    exit 1
fi
install -d -o "$service_user" -g "$service_group" -m 0750 "$STATE_DIR"
temp_db=$STATE_DIR/.delivery-state.sqlite3.$stamp.tmp
python3 tools/messaging/initialize_outbound_mail_delivery_state.py \
    --database "$temp_db" --pretty > "$evidence_dir/database-initialization.json"
chown "$service_user:$service_group" "$temp_db"
chmod 0600 "$temp_db"
mv "$temp_db" "$SUPPRESSION_DATABASE"
db_created=yes

install -d -o root -g root -m 0755 "$DROPIN_DIR"
temp_dropin=$evidence_dir/30-suppression-gate.conf.proposed
write_dropin "$temp_dropin"
install -o root -g root -m 0644 "$temp_dropin" "$DROPIN"
mutated=yes
systemctl daemon-reload
systemctl restart "$SERVICE"
sleep 2

if ! verify_live outbound_mail_gateway_suppressed_server.py; then
    rollback "suppression-aware gateway post-install verification failed"
fi

systemctl show "$SERVICE" \
    -p ActiveState -p SubState -p UnitFileState -p User -p Group -p ExecStart \
    > "$evidence_dir/service-after.txt"
ss -ltnp > "$evidence_dir/listeners-after.txt" 2>&1 || true
systemctl cat "$SERVICE" > "$evidence_dir/unit-after.txt"
journalctl -u "$SERVICE" --since=-5min --no-pager -n 200 \
    > "$evidence_dir/journal-after.txt" 2>&1 || true
record readiness_state suppression_server_active_safe_disabled
record rollback_executed no
record failures 0
(
    cd "$evidence_dir"
    find . -maxdepth 1 -type f ! -name SHA256SUMS -print | sort | xargs sha256sum > SHA256SUMS
)
trap - HUP INT TERM
printf '%s\n' "Suppression-aware outbound-mail server installation completed."
printf '%s\n' "No provider or sender was enabled and no message was sent."
printf 'Evidence: %s\n' "$evidence_dir"
