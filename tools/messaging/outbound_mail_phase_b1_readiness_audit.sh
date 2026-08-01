#!/bin/sh
set -eu

umask 077

REPO_ROOT=${REPO_ROOT:-/opt/edge1-management-interface}
SERVICE_NAME=${SERVICE_NAME:-wwcx-outbound-mail-gateway.service}
EXPECTED_HOST=${EXPECTED_HOST:-edge1.ww.cx}
PHASE_B_PACKAGE_COMMIT=${PHASE_B_PACKAGE_COMMIT:-c55059c2d0230ea273709bbb5a4169b00bb226c1}
TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)

if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root so service and restricted runtime-file metadata can be inspected without reading secret contents." >&2
  exit 77
fi

if [ ! -d "$REPO_ROOT/.git" ]; then
  echo "Repository not found at $REPO_ROOT" >&2
  exit 1
fi

host_fqdn=$(hostname -f 2>/dev/null || hostname)
if [ "$host_fqdn" != "$EXPECTED_HOST" ]; then
  echo "Host mismatch: expected $EXPECTED_HOST, observed $host_fqdn" >&2
  exit 1
fi

if [ -n "${EVIDENCE_DIR:-}" ]; then
  output_dir=$EVIDENCE_DIR
else
  output_dir="/var/lib/wwcx-deployment-evidence/outbound-mail-phase-b1-readiness/$TIMESTAMP"
fi
install -d -m 0700 "$output_dir"

summary="$output_dir/summary.txt"
failures="$output_dir/failures.txt"
: > "$summary"
: > "$failures"

record() {
  printf '%s=%s\n' "$1" "$2" >> "$summary"
}

fail() {
  printf '%s\n' "$1" >> "$failures"
}

branch=$(git -C "$REPO_ROOT" branch --show-current 2>/dev/null || true)
if head_commit=$(git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null); then
  :
else
  head_commit=unknown
  fail "repository HEAD could not be resolved"
fi
record captured_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
record host "$host_fqdn"
record principal "$(id -un)"
record repository "$REPO_ROOT"
record branch "${branch:-detached}"
record head_commit "$head_commit"
record phase_b_package_commit "$PHASE_B_PACKAGE_COMMIT"

if [ "$branch" != main ]; then
  fail "repository branch is not main"
fi
if ! git -C "$REPO_ROOT" diff --quiet || ! git -C "$REPO_ROOT" diff --cached --quiet; then
  fail "tracked repository state is dirty"
fi
if ! git -C "$REPO_ROOT" merge-base --is-ancestor "$PHASE_B_PACKAGE_COMMIT" HEAD; then
  fail "Phase B package commit is not an ancestor of HEAD"
fi

protected_paths='deploy/messaging/install-outbound-mail-preparation-api.sh
deploy/messaging/outbound-mail-preparation-api-nginx.conf.example
deploy/messaging/wwcx-outbound-mail-preparation-api.conf
docs/messaging-operations/outbound-mail-phase-b-preparation-20260801.md
server/outbound_mail_gateway.py
server/outbound_mail_gateway_server.py
server/outbound_mail_preparation_auth.py
tools/outbound_mail_preparation_canary.py
config/messaging/outbound-mail-gateway.json
config/messaging/outbound-mail-policy.json
config/messaging/mail-identities.json'

printf '%s\n' "$protected_paths" > "$output_dir/protected-paths.txt"
if ! git -C "$REPO_ROOT" diff --quiet "$PHASE_B_PACKAGE_COMMIT"..HEAD -- $protected_paths; then
  fail "protected outbound-mail files changed after the approved Phase B package commit"
  git -C "$REPO_ROOT" diff --name-only "$PHASE_B_PACKAGE_COMMIT"..HEAD -- $protected_paths \
    > "$output_dir/protected-path-changes.txt" || true
else
  : > "$output_dir/protected-path-changes.txt"
fi

git -C "$REPO_ROOT" status --short --branch > "$output_dir/git-status.txt" 2>&1 || \
  fail "git status capture failed"
git -C "$REPO_ROOT" log -1 --format='commit=%H%nauthor_date=%aI%ncommitter_date=%cI%nsubject=%s' \
  > "$output_dir/git-head.txt" 2>&1 || fail "git HEAD metadata capture failed"

if ! python3 - "$REPO_ROOT" "$output_dir/committed-safety.json" \
  2> "$output_dir/committed-safety-error.txt" <<'PY'
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
out = pathlib.Path(sys.argv[2])
config = json.loads((root / "config/messaging/outbound-mail-gateway.json").read_text(encoding="utf-8"))
policy = json.loads((root / "config/messaging/outbound-mail-policy.json").read_text(encoding="utf-8"))
identities = json.loads((root / "config/messaging/mail-identities.json").read_text(encoding="utf-8"))

state = {
    "gateway_enabled": config["enabled"],
    "deployment_authorized": config["deployment_authorized"],
    "external_delivery_authorized": config["external_delivery_authorized"],
    "send_endpoint_enabled": config["admin"]["send_endpoint_enabled"],
    "preparation_api_enabled": config["preparation_api"]["enabled"],
    "provider_selected": config["provider"]["selected"],
    "provider_enabled_count": sum(1 for item in config["provider"]["profiles"].values() if item["enabled"]),
    "policy_enabled": policy["enabled"],
    "smtp_cutover_authorized": policy["smtp_cutover_authorized"],
    "allow_external_submission": policy["delivery"]["allow_external_submission"],
    "allow_live_delivery": policy["delivery"]["allow_live_delivery"],
    "outbound_identity_activation_authorized": identities["outbound_activation_authorized"],
    "live_sender_count": sum(1 for item in identities["sender_profiles"].values() if item["outbound_enabled"]),
}
expected = {
    "gateway_enabled": False,
    "deployment_authorized": False,
    "external_delivery_authorized": False,
    "send_endpoint_enabled": False,
    "preparation_api_enabled": False,
    "provider_selected": "none",
    "provider_enabled_count": 0,
    "policy_enabled": False,
    "smtp_cutover_authorized": False,
    "allow_external_submission": False,
    "allow_live_delivery": False,
    "outbound_identity_activation_authorized": False,
    "live_sender_count": 0,
}
out.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
if state != expected:
    raise SystemExit("committed outbound-mail safety state does not match the Phase B1 prerequisite")
PY
then
  fail "committed outbound-mail safety validation failed"
fi

if ! systemctl is-active --quiet "$SERVICE_NAME"; then
  fail "$SERVICE_NAME is not active"
fi
if ! systemctl is-enabled --quiet "$SERVICE_NAME"; then
  fail "$SERVICE_NAME is not enabled"
fi
systemctl status "$SERVICE_NAME" --no-pager -l > "$output_dir/service-status.txt" 2>&1 || true
systemctl show "$SERVICE_NAME" \
  -p ActiveState -p SubState -p UnitFileState -p FragmentPath -p DropInPaths \
  -p User -p Group -p ExecStart -p MainPID -p EnvironmentFiles \
  > "$output_dir/service-properties.txt" 2>&1 || fail "service property capture failed"

if ! systemctl show "$SERVICE_NAME" -p User --value 2>/dev/null | grep -qx 'wwcx-mail-gateway'; then
  fail "service principal is not wwcx-mail-gateway"
fi

ss -lntp > "$output_dir/listeners.txt" 2>&1 || fail "listener inventory failed"
port_addresses="$output_dir/port-8104-addresses.txt"
ss -lnt 2>/dev/null | awk 'NR > 1 {print $4}' | grep -E ':8104$' > "$port_addresses" || true
if ! grep -qx '127.0.0.1:8104' "$port_addresses"; then
  fail "loopback listener 127.0.0.1:8104 was not observed"
fi
if grep -Ev '^127\.0\.0\.1:8104$' "$port_addresses" | grep -q .; then
  fail "port 8104 has a non-approved listener address"
fi

curl -fsS --max-time 5 http://127.0.0.1:8104/outbound-mail/healthz \
  > "$output_dir/health.json" || fail "health endpoint did not return HTTP 200"
curl -fsS --max-time 5 http://127.0.0.1:8104/outbound-mail/status \
  > "$output_dir/status.json" || fail "status endpoint did not return HTTP 200"

api_code=$(curl -sS --max-time 5 -o "$output_dir/unsigned-api-status.json" -w '%{http_code}' \
  http://127.0.0.1:8104/outbound-mail/api/v1/status || true)
record unsigned_api_status_http "$api_code"
if [ "$api_code" != 403 ]; then
  fail "unsigned preparation API status did not return HTTP 403 in Phase A state"
fi

send_code=$(curl -sS --max-time 5 -o "$output_dir/send-probe.json" -w '%{http_code}' \
  -H 'Content-Type: application/json' -d '{}' \
  http://127.0.0.1:8104/outbound-mail/send || true)
record send_probe_http "$send_code"
if [ "$send_code" != 403 ]; then
  fail "send probe did not return HTTP 403"
fi

if ! python3 - "$output_dir/status.json" 2> "$output_dir/status-validation-error.txt" <<'PY'
import json
import pathlib
import sys

status = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
assert status["state"] == "disabled"
assert status["external_delivery_enabled"] is False
assert status["policy_enabled"] is False
assert status["preparation_api"]["enabled"] is False
assert status["preparation_api"]["runtime_secret_configured"] is False
assert status["sender_selection"]["live_sender_count"] == 0
assert not any(item["ready"] for item in status["providers"])
PY
then
  fail "runtime status safety validation failed"
fi

runtime_metadata="$output_dir/runtime-file-metadata.tsv"
printf 'path\tpresent\ttype\tuid\tmode\tbytes\n' > "$runtime_metadata"
for path in \
  /etc/wwcx/outbound-mail-gateway.json \
  /etc/wwcx/outbound-mail-gateway.env \
  /etc/systemd/system/wwcx-outbound-mail-gateway.service.d/20-preparation-api.conf; do
  if [ -e "$path" ] || [ -L "$path" ]; then
    type=$(stat -c %F "$path")
    uid=$(stat -c %u "$path")
    mode=$(stat -c %a "$path")
    bytes=$(stat -c %s "$path")
    printf '%s\tyes\t%s\t%s\t%s\t%s\n' "$path" "$type" "$uid" "$mode" "$bytes" >> "$runtime_metadata"
    fail "unexpected Phase B1 runtime file is present: $path"
  else
    printf '%s\tno\t-\t-\t-\t-\n' "$path" >> "$runtime_metadata"
  fi
done

proxy_matches="$output_dir/proxy-path-matches.txt"
: > "$proxy_matches"
for root in /etc/nginx /etc/apache2 /etc/httpd; do
  if [ -d "$root" ]; then
    grep -R -l --binary-files=without-match 'outbound-mail/api/v1' "$root" 2>/dev/null \
      >> "$proxy_matches" || true
  fi
done
sort -u "$proxy_matches" -o "$proxy_matches"
if [ -s "$proxy_matches" ]; then
  fail "a web-server configuration references the preparation API path"
fi

if [ -s "$failures" ]; then
  record readiness_state not_ready
else
  record readiness_state ready_for_explicit_b1_authorization
fi
record secret_generated no
record secret_read no
record runtime_files_modified no
record service_restarted no
record proxy_modified no
record dns_modified no
record firewall_modified no
record message_sent no

(
  cd "$output_dir"
  find . -type f ! -name SHA256SUMS -print | sort | xargs sha256sum > SHA256SUMS
)
chmod -R go-rwx "$output_dir"

cat "$summary"
if [ -s "$failures" ]; then
  echo "Readiness audit failed:" >&2
  cat "$failures" >&2
  echo "Evidence: $output_dir" >&2
  exit 1
fi

echo "Phase B1 read-only readiness audit passed."
echo "No secret was generated or read, and no runtime or network state was changed."
echo "Evidence: $output_dir"
