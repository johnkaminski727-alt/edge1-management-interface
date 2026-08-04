#!/bin/sh
set -eu
umask 077

ACTION=${ACTION:-audit}
REPO=${REPO:-/opt/edge1-management-interface}
SERVICE=${SERVICE:-wwcx-outbound-mail-gateway.service}
EXPECTED_HOST=${EXPECTED_HOST:-edge1.ww.cx}
EXPECTED_COMMIT=${EXPECTED_COMMIT:-}
RUNTIME_MIGRATION_AUTHORIZED=${RUNTIME_MIGRATION_AUTHORIZED:-no}
SOURCE_CONFIG=${SOURCE_CONFIG:-/etc/wwcx/outbound-mail-gateway.json}
SOURCE_IDENTITIES=${SOURCE_IDENTITIES:-$REPO/config/messaging/mail-identities.json}
CONFIG_ROOT=${CONFIG_ROOT:-/etc/wwcx}
STATE_ROOT=${STATE_ROOT:-/var/lib/wwcx-outbound-mail}
RUNTIME_CONFIG=${RUNTIME_CONFIG:-$CONFIG_ROOT/outbound-mail-gateway-runtime.json}
RUNTIME_POLICY=${RUNTIME_POLICY:-$CONFIG_ROOT/outbound-mail-policy-runtime.json}
RUNTIME_IDENTITIES=${RUNTIME_IDENTITIES:-$CONFIG_ROOT/mail-identities-runtime.json}
RUNTIME_AUDIT=${RUNTIME_AUDIT:-$STATE_ROOT/audit.jsonl}
RUNTIME_NONCES=${RUNTIME_NONCES:-$STATE_ROOT/preparation-nonces.sqlite3}
SUPPRESSION_DATABASE=${SUPPRESSION_DATABASE:-$STATE_ROOT/delivery-state.sqlite3}
DROPIN_DIR=${DROPIN_DIR:-/etc/systemd/system/$SERVICE.d}
DROPIN=${DROPIN:-$DROPIN_DIR/40-runtime-paths.conf}
EVIDENCE_ROOT=${EVIDENCE_ROOT:-/var/lib/wwcx-deployment-evidence/outbound-mail-runtime-migration}
LISTEN_HOST=${LISTEN_HOST:-127.0.0.1}
LISTEN_PORT=${LISTEN_PORT:-8104}

case "$ACTION" in
    audit|install|verify|disable) ;;
    *) echo "ACTION must be audit, install, verify, or disable." >&2; exit 2 ;;
esac
for path_value in "$REPO" "$SOURCE_CONFIG" "$SOURCE_IDENTITIES" "$CONFIG_ROOT" "$STATE_ROOT" "$RUNTIME_CONFIG" "$RUNTIME_POLICY" "$RUNTIME_IDENTITIES" "$RUNTIME_AUDIT" "$RUNTIME_NONCES" "$SUPPRESSION_DATABASE" "$DROPIN_DIR" "$DROPIN" "$EVIDENCE_ROOT"; do
    case "$path_value" in *" "*|*"	"*) echo "Configured paths must not contain whitespace." >&2; exit 1 ;; esac
done

[ "$(id -u)" -eq 0 ] || { echo "Runtime migration must run as root." >&2; exit 1; }
host=$(hostname -f 2>/dev/null || hostname)
[ "$host" = "$EXPECTED_HOST" ] || { echo "Host mismatch: expected $EXPECTED_HOST but found $host" >&2; exit 1; }

cd "$REPO"
branch=$(git branch --show-current)
head_commit=$(git rev-parse HEAD)
status=$(git status --porcelain --untracked-files=all)
[ "$branch" = main ] || { echo "Repository branch must be main." >&2; exit 1; }
[ -z "$status" ] || { echo "Repository working tree must be clean." >&2; git status --short >&2; exit 1; }
[ -n "$EXPECTED_COMMIT" ] && [ "$head_commit" = "$EXPECTED_COMMIT" ] || { echo "Repository HEAD does not match explicit EXPECTED_COMMIT." >&2; exit 1; }

for required in \
    server/outbound_mail_gateway_runtime_server.py \
    server/outbound_mail_runtime_application.py \
    server/outbound_mail_runtime_paths.py \
    server/outbound_mail_gateway_suppressed_server.py \
    server/outbound_mail_suppression_gate.py \
    server/outbound_mail_delivery_events.py \
    tools/messaging/build_outbound_mail_disabled_runtime_bundle.py \
    tools/messaging/initialize_outbound_mail_delivery_state.py \
    tests/validate_outbound_mail_disabled_runtime_bundle.py \
    tests/validate_outbound_mail_runtime_paths.py
 do
    [ -f "$required" ] || { echo "Required repository file is absent: $required" >&2; exit 1; }
 done
[ -f "$SOURCE_CONFIG" ] && [ ! -L "$SOURCE_CONFIG" ] || { echo "Existing preparation runtime config is absent or unsafe." >&2; exit 1; }
[ -f "$SOURCE_IDENTITIES" ] && [ ! -L "$SOURCE_IDENTITIES" ] || { echo "Source identities are absent or unsafe." >&2; exit 1; }

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
bundle_dir=$evidence_dir/runtime-bundle
install -d -m 0700 "$evidence_dir"
summary=$evidence_dir/summary.txt
failures=$evidence_dir/failures.txt
: > "$summary"
: > "$failures"
record() { printf '%s=%s\n' "$1" "$2" | tee -a "$summary"; }
manifest() {
    (
        cd "$evidence_dir"
        find . -type f ! -name SHA256SUMS -print | sort | xargs sha256sum > SHA256SUMS
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
record source_config "$SOURCE_CONFIG"
record runtime_config "$RUNTIME_CONFIG"
record state_root "$STATE_ROOT"
record provider_credentials_read no
record hmac_secret_read no
record source_config_modified no
record provider_or_sender_enabled no
record external_delivery_enabled no
record message_prepared no
record message_sent no
record dns_modified no
record firewall_modified no
record public_listener_added no

systemctl show "$SERVICE" -p ActiveState -p SubState -p UnitFileState -p User -p Group -p ExecStart > "$evidence_dir/service-before.txt"
systemctl cat "$SERVICE" > "$evidence_dir/unit-before.txt"
ss -ltnp > "$evidence_dir/listeners-before.txt" 2>&1 || true
source_config_sha=$(sha256sum "$SOURCE_CONFIG" | awk '{print $1}')
record source_config_sha256 "$source_config_sha"

paths_json=$evidence_dir/source-paths.json
python3 - "$SOURCE_CONFIG" "$REPO" <<'PY' > "$paths_json"
import json
import pathlib
import sys
config = json.load(open(sys.argv[1], encoding="utf-8"))
root = pathlib.Path(sys.argv[2]).resolve()
def resolve(value):
    path = pathlib.Path(value)
    if path.is_absolute():
        raise SystemExit("source runtime paths must remain repository-relative before migration")
    candidate = (root / path).resolve()
    if candidate != root and root not in candidate.parents:
        raise SystemExit("source runtime path escaped repository")
    return str(candidate)
print(json.dumps({
    "policy": resolve(config["paths"]["policy"]),
    "audit": resolve(config["paths"]["audit_jsonl"]),
    "nonce": resolve(config["preparation_api"]["nonce_store"]),
}, indent=2, sort_keys=True))
PY
source_policy=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["policy"])' "$paths_json")
source_audit=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["audit"])' "$paths_json")
source_nonce=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["nonce"])' "$paths_json")
for source_path in "$source_policy" "$source_audit" "$source_nonce"; do
    case "$source_path" in *" "*|*"	"*) echo "Resolved source path contains whitespace." >&2; exit 1 ;; esac
done
[ -f "$source_policy" ] && [ ! -L "$source_policy" ] || { echo "Existing runtime policy is absent or unsafe." >&2; exit 1; }

python3 -m py_compile \
    server/outbound_mail_gateway_runtime_server.py \
    server/outbound_mail_runtime_application.py \
    server/outbound_mail_runtime_paths.py \
    tools/messaging/build_outbound_mail_disabled_runtime_bundle.py
python3 tests/validate_outbound_mail_disabled_runtime_bundle.py > "$evidence_dir/runtime-bundle-validation.txt"
python3 tests/validate_outbound_mail_runtime_paths.py > "$evidence_dir/runtime-path-validation.txt" 2>&1
python3 tools/messaging/build_outbound_mail_disabled_runtime_bundle.py \
    --existing-config "$SOURCE_CONFIG" \
    --policy "$source_policy" \
    --identities "$SOURCE_IDENTITIES" \
    --config-root "$CONFIG_ROOT" \
    --state-root "$STATE_ROOT" \
    --output-dir "$bundle_dir" \
    > "$evidence_dir/runtime-bundle-build.json"

systemctl is-active --quiet "$SERVICE" || { echo "Gateway service is not active before migration." >&2; exit 1; }
if ss -ltnH | awk -v port=":$LISTEN_PORT" '$4 ~ port "$" {print $4}' | grep -Ev '^(127\.0\.0\.1|\[::1\]):' >/dev/null 2>&1; then
    echo "An external listener exists on the gateway port." >&2
    exit 1
fi

write_dropin() {
    target=$1
    cat > "$target" <<EOF
[Service]
ExecStart=
ExecStart=/usr/bin/python3 $REPO/server/outbound_mail_gateway_runtime_server.py --config $RUNTIME_CONFIG --identities $RUNTIME_IDENTITIES --config-root $CONFIG_ROOT --state-root $STATE_ROOT --suppression-database $SUPPRESSION_DATABASE --host $LISTEN_HOST --port $LISTEN_PORT
EOF
}

verify_state_database() {
    python3 - "$SUPPRESSION_DATABASE" <<'PY'
import pathlib
import sqlite3
import sys
path = pathlib.Path(sys.argv[1])
if not path.is_file() or path.is_symlink():
    raise SystemExit(1)
connection = sqlite3.connect(path)
try:
    tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'") if not row[0].startswith("sqlite_")}
finally:
    connection.close()
if tables != {"delivery_events", "recipient_delivery_state"}:
    raise SystemExit(1)
PY
}

verify_live() {
    systemctl is-active --quiet "$SERVICE" || return 1
    exec_start=$(systemctl show "$SERVICE" -p ExecStart --value)
    printf '%s\n' "$exec_start" > "$evidence_dir/execstart-after.txt"
    printf '%s' "$exec_start" | grep -F outbound_mail_gateway_runtime_server.py >/dev/null || return 1
    for runtime_file in "$RUNTIME_CONFIG" "$RUNTIME_POLICY" "$RUNTIME_IDENTITIES"; do
        [ -f "$runtime_file" ] && [ ! -L "$runtime_file" ] || return 1
        [ "$(stat -c '%U' "$runtime_file")" = root ] || return 1
        mode=$(stat -c '%a' "$runtime_file")
        [ "$mode" = 644 ] || return 1
    done
    [ -f "$RUNTIME_AUDIT" ] && [ ! -L "$RUNTIME_AUDIT" ] || return 1
    [ "$(stat -c '%U' "$RUNTIME_AUDIT")" = "$service_user" ] || return 1
    [ "$(stat -c '%G' "$RUNTIME_AUDIT")" = "$service_group" ] || return 1
    [ "$(stat -c '%a' "$RUNTIME_AUDIT")" = 600 ] || return 1
    if [ -e "$RUNTIME_NONCES" ]; then
        [ -f "$RUNTIME_NONCES" ] && [ ! -L "$RUNTIME_NONCES" ] || return 1
        [ "$(stat -c '%U' "$RUNTIME_NONCES")" = "$service_user" ] || return 1
        [ "$(stat -c '%G' "$RUNTIME_NONCES")" = "$service_group" ] || return 1
        [ "$(stat -c '%a' "$RUNTIME_NONCES")" = 600 ] || return 1
    fi
    [ "$(stat -c '%U' "$SUPPRESSION_DATABASE")" = "$service_user" ] || return 1
    [ "$(stat -c '%G' "$SUPPRESSION_DATABASE")" = "$service_group" ] || return 1
    [ "$(stat -c '%a' "$SUPPRESSION_DATABASE")" = 600 ] || return 1
    verify_state_database || return 1
    health_code=$(curl --silent --show-error --max-time 8 --output "$evidence_dir/health.json" --write-out '%{http_code}' "http://$LISTEN_HOST:$LISTEN_PORT/outbound-mail/healthz")
    [ "$health_code" = 200 ] || return 1
    status_code=$(curl --silent --show-error --max-time 8 --output "$evidence_dir/status.json" --write-out '%{http_code}' "http://$LISTEN_HOST:$LISTEN_PORT/outbound-mail/status")
    [ "$status_code" = 200 ] || return 1
    unsigned_code=$(curl --silent --show-error --max-time 8 --output "$evidence_dir/unsigned-status.json" --write-out '%{http_code}' "http://$LISTEN_HOST:$LISTEN_PORT/outbound-mail/api/v1/status")
    [ "$unsigned_code" = 401 ] || return 1
    send_code=$(curl --silent --show-error --max-time 8 --header 'Content-Type: application/json' \
        --data '{"to":["runtime-migration-canary@example.invalid"],"subject":"Disabled runtime migration canary","body":"This request must remain disabled.","message_class":"business_correspondence","confirm_send":true}' \
        --output "$evidence_dir/disabled-send.json" --write-out '%{http_code}' \
        "http://$LISTEN_HOST:$LISTEN_PORT/outbound-mail/send")
    [ "$send_code" = 403 ] || return 1
    python3 - "$evidence_dir/status.json" "$evidence_dir/disabled-send.json" <<'PY'
import json
import sys
status = json.load(open(sys.argv[1], encoding="utf-8"))
send = json.load(open(sys.argv[2], encoding="utf-8"))
prep = status.get("preparation_api", {})
assert prep.get("enabled") is True
assert prep.get("runtime_secret_configured") is True
assert status.get("external_delivery_enabled") is False
assert status.get("policy_enabled") is False
assert not any(item.get("ready") for item in status.get("providers", []))
assert status.get("sender_selection", {}).get("live_sender_count", 0) == 0
assert send.get("error") == "delivery_disabled"
PY
    [ "$(sha256sum "$SOURCE_CONFIG" | awk '{print $1}')" = "$source_config_sha" ] || return 1
    if ss -ltnH | awk -v port=":$LISTEN_PORT" '$4 ~ port "$" {print $4}' | grep -Ev '^(127\.0\.0\.1|\[::1\]):' >/dev/null 2>&1; then
        return 1
    fi
}

if [ "$ACTION" = audit ]; then
    current_exec=$(systemctl show "$SERVICE" -p ExecStart --value)
    case "$current_exec" in
        *outbound_mail_gateway_runtime_server.py*) state=installed ;;
        *) state=not_installed ;;
    esac
    record readiness_state "$state"
    record failures 0
    manifest
    echo "Disabled runtime migration audit completed: $evidence_dir"
    exit 0
fi

if [ "$ACTION" = verify ]; then
    if ! verify_live; then
        record readiness_state verification_failed
        record failures 1
        manifest
        exit 1
    fi
    record readiness_state runtime_migration_active_safe_disabled
    record failures 0
    manifest
    echo "Disabled runtime migration verification completed: $evidence_dir"
    exit 0
fi

[ "$RUNTIME_MIGRATION_AUTHORIZED" = yes ] || { echo "Install or disable requires RUNTIME_MIGRATION_AUTHORIZED=yes." >&2; exit 1; }

if [ "$ACTION" = disable ]; then
    [ -f "$DROPIN" ] && [ ! -L "$DROPIN" ] || { echo "Runtime migration drop-in is absent or unsafe." >&2; exit 1; }
    expected_dropin=$evidence_dir/expected-dropin.conf
    write_dropin "$expected_dropin"
    cmp -s "$expected_dropin" "$DROPIN" || { echo "Runtime migration drop-in drift detected; refusing disable." >&2; exit 1; }
    mv "$DROPIN" "$evidence_dir/40-runtime-paths.conf.disabled"
    systemctl daemon-reload
    systemctl restart "$SERVICE"
    sleep 2
    systemctl is-active --quiet "$SERVICE" || { echo "Prior gateway did not recover after disable." >&2; exit 1; }
    exec_start=$(systemctl show "$SERVICE" -p ExecStart --value)
    printf '%s' "$exec_start" | grep -Fv outbound_mail_gateway_runtime_server.py >/dev/null || { echo "Runtime entrypoint remained active after disable." >&2; exit 1; }
    record readiness_state runtime_migration_disabled_files_preserved
    record failures 0
    systemctl show "$SERVICE" -p ActiveState -p SubState -p ExecStart > "$evidence_dir/service-after.txt"
    manifest
    echo "Disabled runtime migration disable completed: $evidence_dir"
    exit 0
fi

for destination in "$RUNTIME_CONFIG" "$RUNTIME_POLICY" "$RUNTIME_IDENTITIES" "$RUNTIME_AUDIT" "$RUNTIME_NONCES" "$DROPIN"; do
    [ ! -e "$destination" ] || { echo "Migration destination already exists: $destination" >&2; exit 1; }
done

runtime_config_created=no
runtime_policy_created=no
runtime_identities_created=no
runtime_audit_created=no
runtime_nonces_created=no
suppression_created=no
dropin_created=no
mutated=no
completed=no
rollback() {
    reason=$1
    trap - 0 HUP INT TERM
    set +e
    if [ "$dropin_created" = yes ] && [ -f "$DROPIN" ]; then mv "$DROPIN" "$evidence_dir/40-runtime-paths.conf.rolled-back"; fi
    systemctl daemon-reload
    systemctl start "$SERVICE"
    for item in \
        "$runtime_config_created:$RUNTIME_CONFIG" \
        "$runtime_policy_created:$RUNTIME_POLICY" \
        "$runtime_identities_created:$RUNTIME_IDENTITIES" \
        "$runtime_audit_created:$RUNTIME_AUDIT" \
        "$runtime_nonces_created:$RUNTIME_NONCES" \
        "$suppression_created:$SUPPRESSION_DATABASE"
    do
        flag=${item%%:*}
        path=${item#*:}
        if [ "$flag" = yes ] && [ -e "$path" ]; then mv "$path" "$path.rolled-back-$stamp"; fi
    done
    printf '%s\n' "$reason" >> "$failures"
    record rollback_executed yes
    record rollback_reason "$reason"
    record source_config_preserved "$([ "$(sha256sum "$SOURCE_CONFIG" | awk '{print $1}')" = "$source_config_sha" ] && echo yes || echo no)"
    systemctl show "$SERVICE" -p ActiveState -p SubState -p ExecStart > "$evidence_dir/service-after-rollback.txt" 2>&1
    manifest
    exit 1
}
on_exit() {
    rc=$1
    trap - 0 HUP INT TERM
    if [ "$rc" -ne 0 ] && [ "$mutated" = yes ] && [ "$completed" != yes ]; then rollback "automatic rollback after runtime migration exit $rc"; fi
    exit "$rc"
}
trap 'on_exit $?' 0
trap 'exit 130' HUP INT TERM

if [ ! -d "$CONFIG_ROOT" ]; then install -d -o root -g root -m 0755 "$CONFIG_ROOT"; fi
[ -d "$CONFIG_ROOT" ] && [ ! -L "$CONFIG_ROOT" ] && [ "$(stat -c '%U' "$CONFIG_ROOT")" = root ] || { echo "Config root is unsafe." >&2; exit 1; }
config_mode=$(stat -c '%a' "$CONFIG_ROOT")
case "$config_mode" in *2|*3|*6|*7) echo "Config root is group/world writable." >&2; exit 1 ;; esac
if [ ! -d "$STATE_ROOT" ]; then install -d -o "$service_user" -g "$service_group" -m 0750 "$STATE_ROOT"; fi
[ -d "$STATE_ROOT" ] && [ ! -L "$STATE_ROOT" ] && [ "$(stat -c '%U' "$STATE_ROOT")" = "$service_user" ] || { echo "State root is unsafe." >&2; exit 1; }
install -d -o root -g root -m 0755 "$DROPIN_DIR"

mutated=yes
systemctl stop "$SERVICE"

if [ -f "$source_audit" ]; then
    install -o "$service_user" -g "$service_group" -m 0600 "$source_audit" "$RUNTIME_AUDIT"
else
    install -o "$service_user" -g "$service_group" -m 0600 /dev/null "$RUNTIME_AUDIT"
fi
runtime_audit_created=yes

if [ -f "$source_nonce" ]; then
    temp_nonce=$STATE_ROOT/.preparation-nonces.sqlite3.$stamp.tmp
    python3 - "$source_nonce" "$temp_nonce" <<'PY'
import sqlite3
import sys
source = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
destination = sqlite3.connect(sys.argv[2])
try:
    source.backup(destination)
finally:
    destination.close()
    source.close()
PY
    chown "$service_user:$service_group" "$temp_nonce"
    chmod 0600 "$temp_nonce"
    mv "$temp_nonce" "$RUNTIME_NONCES"
    runtime_nonces_created=yes
fi

if [ ! -e "$SUPPRESSION_DATABASE" ]; then
    temp_suppression=$STATE_ROOT/.delivery-state.sqlite3.$stamp.tmp
    python3 tools/messaging/initialize_outbound_mail_delivery_state.py --database "$temp_suppression" --pretty > "$evidence_dir/suppression-initialization.json"
    chown "$service_user:$service_group" "$temp_suppression"
    chmod 0600 "$temp_suppression"
    mv "$temp_suppression" "$SUPPRESSION_DATABASE"
    suppression_created=yes
else
    [ -f "$SUPPRESSION_DATABASE" ] && [ ! -L "$SUPPRESSION_DATABASE" ] || rollback "existing suppression database is unsafe"
    [ "$(stat -c '%U' "$SUPPRESSION_DATABASE")" = "$service_user" ] || rollback "existing suppression database owner mismatch"
    [ "$(stat -c '%G' "$SUPPRESSION_DATABASE")" = "$service_group" ] || rollback "existing suppression database group mismatch"
    [ "$(stat -c '%a' "$SUPPRESSION_DATABASE")" = 600 ] || rollback "existing suppression database mode mismatch"
    verify_state_database || rollback "existing suppression database schema mismatch"
fi

install -o root -g root -m 0644 "$bundle_dir/outbound-mail-gateway-runtime.json" "$RUNTIME_CONFIG"
runtime_config_created=yes
install -o root -g root -m 0644 "$bundle_dir/outbound-mail-policy-runtime.json" "$RUNTIME_POLICY"
runtime_policy_created=yes
install -o root -g root -m 0644 "$bundle_dir/mail-identities-runtime.json" "$RUNTIME_IDENTITIES"
runtime_identities_created=yes
proposed_dropin=$evidence_dir/40-runtime-paths.conf.proposed
write_dropin "$proposed_dropin"
install -o root -g root -m 0644 "$proposed_dropin" "$DROPIN"
dropin_created=yes
systemctl daemon-reload
systemctl start "$SERVICE"
sleep 2
verify_live || rollback "runtime migration post-install verification failed"

systemctl show "$SERVICE" -p ActiveState -p SubState -p UnitFileState -p User -p Group -p ExecStart > "$evidence_dir/service-after.txt"
systemctl cat "$SERVICE" > "$evidence_dir/unit-after.txt"
ss -ltnp > "$evidence_dir/listeners-after.txt" 2>&1 || true
journalctl -u "$SERVICE" --since=-5min --no-pager -n 250 > "$evidence_dir/journal-after.txt" 2>&1 || true
record readiness_state runtime_migration_active_safe_disabled
record rollback_executed no
record source_config_preserved yes
record failures 0
manifest
completed=yes
trap - 0 HUP INT TERM
printf '%s\n' "Disabled outbound-mail runtime migration completed."
printf '%s\n' "The original preparation config remains unchanged and no message was sent."
printf 'Evidence: %s\n' "$evidence_dir"
