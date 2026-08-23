#!/bin/sh
set -eu
umask 077

EXPECTED_USER=${EDGE1_EXPECTED_OPERATOR_USER:-edge1-operator}
TUNNEL_CLIENT=${TUNNEL_CLIENT_BIN:-/usr/local/bin/tunnel-client}
LAUNCHER=${EDGE1_TUNNEL_LAUNCHER:-/usr/local/libexec/edge1-tunnel/edge1-secure-mcp-tunnel.sh}
CONFIG=${EDGE1_TUNNEL_CONFIG:-/etc/edge1-tunnel/tunnel-client.yaml}
SERVICE_UNIT=${EDGE1_TUNNEL_SERVICE_UNIT:-/etc/systemd/system/edge1-secure-mcp-tunnel.service}
TUNNEL_ID_FILE=${EDGE1_TUNNEL_ID_FILE:-/etc/edge1-tunnel/tunnel-id}
API_KEY_FILE=${EDGE1_TUNNEL_API_KEY_FILE:-/etc/edge1-tunnel/runtime-api-key}
TOKEN_FILE=${EDGE1_OPERATOR_MCP_TOKEN_FILE:-/etc/edge1-operator/mcp-token}
EXPECTED_CLIENT_SHA=937347720ef32ef3ef2f68f4496b2dd7917ca5e575452ed87a4ce78d0262a100
EXPECTED_CLIENT_VERSION='0.0.10+105e17a79a36e4e5c897fd698ed2b8dbf935b144'
EXPECTED_LAUNCHER_SHA=c0b7788bc40c3668b75b6f6410885bd9ce89a39e08c962b80a2e86f4497868f4
EXPECTED_CONFIG_SHA=afd2572a7a87f653e746350f4ae75e62244684e1a981aa429165014e755a2ede
EXPECTED_SERVICE_SHA=e8070f5acca3b747ec61a8a0a0c83982be8731262d88907c4b29bb280a58042d
MCP_URL=http://127.0.0.1:8102/mcp

fail() {
    echo "EDGE1_TUNNEL_COMPAT_DOCTOR=FAIL"
    echo "reason=$*"
    exit 1
}

require_metadata() {
    path=$1
    expected=$2
    actual=$(stat -c '%a:%U:%G' "$path" 2>/dev/null || true)
    [ "$actual" = "$expected" ] || fail "unexpected metadata for $path: $actual"
}

[ "$(id -un)" = "$EXPECTED_USER" ] || fail "run as $EXPECTED_USER"
[ -x "$TUNNEL_CLIENT" ] || fail "tunnel-client unavailable"
[ -x "$LAUNCHER" ] || fail "Edge1 tunnel launcher unavailable"
[ -r "$CONFIG" ] || fail "tunnel config unreadable"
[ -r "$SERVICE_UNIT" ] || fail "Edge1 tunnel service unit unreadable"
[ -r "$TUNNEL_ID_FILE" ] || fail "tunnel id unreadable"
[ -r "$API_KEY_FILE" ] || fail "runtime API key unreadable"
[ -r "$TOKEN_FILE" ] || fail "Edge1 MCP token unreadable"
for command in sha256sum python3 stat; do
    command -v "$command" >/dev/null 2>&1 || fail "$command unavailable"
done

require_metadata "$TUNNEL_CLIENT" '755:root:root'
require_metadata "$LAUNCHER" '755:root:root'
require_metadata "$CONFIG" '640:root:edge1-operator'
require_metadata "$SERVICE_UNIT" '644:root:root'
require_metadata "$TUNNEL_ID_FILE" '640:root:edge1-operator'
require_metadata "$API_KEY_FILE" '640:root:edge1-operator'
require_metadata "$TOKEN_FILE" '600:edge1-operator:edge1-operator'

CLIENT_SHA=$(sha256sum "$TUNNEL_CLIENT" | awk '{print $1}')
CLIENT_VERSION=$($TUNNEL_CLIENT --version 2>&1 | sed -n '1p')
LAUNCHER_SHA=$(sha256sum "$LAUNCHER" | awk '{print $1}')
CONFIG_SHA=$(sha256sum "$CONFIG" | awk '{print $1}')
SERVICE_SHA=$(sha256sum "$SERVICE_UNIT" | awk '{print $1}')

echo "tunnel_client_version=$CLIENT_VERSION"
echo "tunnel_client_sha256=$CLIENT_SHA"
echo "launcher_sha256=$LAUNCHER_SHA"
echo "config_sha256=$CONFIG_SHA"
echo "service_unit_sha256=$SERVICE_SHA"

[ "$CLIENT_SHA" = "$EXPECTED_CLIENT_SHA" ] || fail "unreviewed tunnel-client binary"
printf '%s\n' "$CLIENT_VERSION" | grep -Fq "$EXPECTED_CLIENT_VERSION" || \
    fail "unreviewed tunnel-client version"
[ "$LAUNCHER_SHA" = "$EXPECTED_LAUNCHER_SHA" ] || fail "installed tunnel launcher drifted from reviewed content"
[ "$CONFIG_SHA" = "$EXPECTED_CONFIG_SHA" ] || fail "installed tunnel config drifted from reviewed content"
[ "$SERVICE_SHA" = "$EXPECTED_SERVICE_SHA" ] || fail "installed tunnel service unit drifted from reviewed content"

# Independently prove the accepted loopback bearer boundary. GET /mcp is 401
# without the bearer and 405 with the valid bearer because this transport is
# POST-only. OAuth metadata paths remain absent by design.
EDGE1_MCP_URL="$MCP_URL" EDGE1_MCP_TOKEN_FILE="$TOKEN_FILE" python3 - <<'PY'
import os
import urllib.error
import urllib.request

mcp_url = os.environ["EDGE1_MCP_URL"]
token_path = os.environ["EDGE1_MCP_TOKEN_FILE"]
with open(token_path, "r", encoding="utf-8") as fh:
    token = fh.read().strip()
if len(token) < 32 or any(ch.isspace() for ch in token):
    raise SystemExit("invalid local MCP token")


def status(url, authorization=False):
    headers = {}
    if authorization:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, method="GET", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=2) as resp:
            return resp.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except urllib.error.URLError as exc:
        raise SystemExit(f"local MCP probe failed: {type(exc.reason).__name__}") from exc

base = "http://127.0.0.1:8102"
checks = {
    "unauthenticated_mcp": status(mcp_url, authorization=False),
    "authenticated_mcp": status(mcp_url, authorization=True),
    "oauth_path_candidate": status(base + "/.well-known/oauth-protected-resource/mcp", authorization=False),
    "oauth_root_candidate": status(base + "/.well-known/oauth-protected-resource", authorization=False),
}
for name, code in checks.items():
    print(f"{name}_http={code}")
if checks["unauthenticated_mcp"] != 401:
    raise SystemExit("unauthenticated MCP boundary changed")
if checks["authenticated_mcp"] != 405:
    raise SystemExit("authenticated MCP bearer boundary changed")
if checks["oauth_path_candidate"] != 404 or checks["oauth_root_candidate"] != 404:
    raise SystemExit("OAuth metadata discovery contract changed; re-review required")
PY

TMP=$(mktemp "${TMPDIR:-/tmp}/edge1-tunnel-doctor.XXXXXX")
trap 'rm -f "$TMP"' EXIT HUP INT TERM

set +e
"$LAUNCHER" doctor >"$TMP" 2>&1
DOCTOR_RC=$?
set -e

echo "raw_doctor_rc=$DOCTOR_RC"

# This validator is intentionally pinned to the exact old client build whose
# doctor-only OAuth false negative was reviewed. Raw success from this pinned
# build means the environment/authentication contract changed and requires a
# new review; it is not silently accepted.
[ "$DOCTOR_RC" -eq 2 ] || fail "pinned raw doctor result changed; re-review required (rc=$DOCTOR_RC)"

FAILED_CHECKS=$(sed -n 's/^FAILED_CHECKS[[:space:]]*//p' "$TMP" | tail -n 1)
[ "$FAILED_CHECKS" = "oauth_metadata" ] || \
    fail "raw doctor failed checks are not exactly oauth_metadata"

grep -Fq 'CHECK oauth_metadata' "$TMP" || fail "oauth_metadata result missing"
grep -Fq 'HTTP 404 from http://127.0.0.1:8102/.well-known/oauth-protected-resource/mcp' "$TMP" || \
    fail "doctor OAuth failure is not the reviewed path-specific 404"

echo "compatibility_override=known_0.0.10_optional_oauth_metadata_false_negative"
echo "EDGE1_TUNNEL_COMPAT_DOCTOR=PASS"
