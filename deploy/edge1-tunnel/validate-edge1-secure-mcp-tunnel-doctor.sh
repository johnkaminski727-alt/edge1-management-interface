#!/bin/sh
set -eu
umask 077

EXPECTED_USER=${EDGE1_EXPECTED_OPERATOR_USER:-edge1-operator}
TUNNEL_CLIENT=${TUNNEL_CLIENT_BIN:-/usr/local/bin/tunnel-client}
LAUNCHER=${EDGE1_TUNNEL_LAUNCHER:-/usr/local/libexec/edge1-tunnel/edge1-secure-mcp-tunnel.sh}
CONFIG=${EDGE1_TUNNEL_CONFIG:-/etc/edge1-tunnel/tunnel-client.yaml}
TOKEN_FILE=${EDGE1_OPERATOR_MCP_TOKEN_FILE:-/etc/edge1-operator/mcp-token}
EXPECTED_CLIENT_SHA=937347720ef32ef3ef2f68f4496b2dd7917ca5e575452ed87a4ce78d0262a100
EXPECTED_CLIENT_VERSION='0.0.10+105e17a79a36e4e5c897fd698ed2b8dbf935b144'
MCP_URL=http://127.0.0.1:8102/mcp

fail() {
    echo "EDGE1_TUNNEL_COMPAT_DOCTOR=FAIL"
    echo "reason=$*"
    exit 1
}

[ "$(id -un)" = "$EXPECTED_USER" ] || fail "run as $EXPECTED_USER"
[ -x "$TUNNEL_CLIENT" ] || fail "tunnel-client unavailable"
[ -x "$LAUNCHER" ] || fail "Edge1 tunnel launcher unavailable"
[ -r "$CONFIG" ] || fail "tunnel config unreadable"
[ -r "$TOKEN_FILE" ] || fail "Edge1 MCP token unreadable"
command -v sha256sum >/dev/null 2>&1 || fail "sha256sum unavailable"
command -v python3 >/dev/null 2>&1 || fail "python3 unavailable"

CLIENT_SHA=$(sha256sum "$TUNNEL_CLIENT" | awk '{print $1}')
CLIENT_VERSION=$($TUNNEL_CLIENT --version 2>&1 | sed -n '1p')

echo "tunnel_client_version=$CLIENT_VERSION"
echo "tunnel_client_sha256=$CLIENT_SHA"

# The Edge1 transport deliberately uses a static bearer header for both normal
# MCP traffic and discovery/probe traffic. This avoids adding a second OAuth
# authority to the already-authenticated loopback Operator service.
[ "$(grep -Fxc '      url: http://127.0.0.1:8102/mcp' "$CONFIG" || true)" -eq 1 ] || \
    fail "unexpected main MCP target"
[ "$(grep -Fc 'Authorization: env:EDGE1_MCP_AUTHORIZATION' "$CONFIG" || true)" -eq 2 ] || \
    fail "runtime/discovery bearer header configuration is not exact"

TMP=$(mktemp "${TMPDIR:-/tmp}/edge1-tunnel-doctor.XXXXXX")
trap 'rm -f "$TMP"' EXIT HUP INT TERM

set +e
"$LAUNCHER" doctor >"$TMP" 2>&1
DOCTOR_RC=$?
set -e

echo "raw_doctor_rc=$DOCTOR_RC"

if [ "$DOCTOR_RC" -eq 0 ]; then
    echo "compatibility_override=not_needed"
    echo "EDGE1_TUNNEL_COMPAT_DOCTOR=PASS"
    exit 0
fi

# tunnel-client 0.0.10 at 105e17a has a known doctor-only false negative:
# every HTTP target is required to expose OAuth PRMD. Later upstream behavior
# treats all-404 PRMD discovery as optional for plain/non-OAuth MCP servers.
# Never apply this compatibility rule to a different binary or to any other
# failed check.
[ "$CLIENT_SHA" = "$EXPECTED_CLIENT_SHA" ] || fail "raw doctor failed on an unreviewed tunnel-client binary"
printf '%s\n' "$CLIENT_VERSION" | grep -Fq "$EXPECTED_CLIENT_VERSION" || \
    fail "raw doctor failed on an unreviewed tunnel-client version"
[ "$DOCTOR_RC" -eq 2 ] || fail "unexpected raw doctor exit code $DOCTOR_RC"

FAILED_CHECKS=$(sed -n 's/^FAILED_CHECKS[[:space:]]*//p' "$TMP" | tail -n 1)
[ "$FAILED_CHECKS" = "oauth_metadata" ] || \
    fail "raw doctor failed checks are not exactly oauth_metadata"

grep -Fq 'CHECK oauth_metadata' "$TMP" || fail "oauth_metadata result missing"
grep -Fq 'HTTP 404 from http://127.0.0.1:8102/.well-known/oauth-protected-resource/mcp' "$TMP" || \
    fail "doctor OAuth failure is not the reviewed path-specific 404"

# Independently verify the local server contract without exposing the bearer
# value in argv, output, Git, or the tunnel-client doctor report.
EDGE1_MCP_URL="$MCP_URL" EDGE1_MCP_TOKEN_FILE="$TOKEN_FILE" python3 - <<'PY'
import os
import urllib.error
import urllib.request

mcp_url = os.environ["EDGE1_MCP_URL"]
token_path = os.environ["EDGE1_MCP_TOKEN_FILE"]
with open(token_path, "r", encoding="utf-8") as fh:
    token = fh.read().strip()
if len(token) < 32:
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

base = "http://127.0.0.1:8102"
checks = {
    "unauthenticated_mcp": status(mcp_url, authorization=False),
    "oauth_path_candidate": status(base + "/.well-known/oauth-protected-resource/mcp", authorization=True),
    "oauth_root_candidate": status(base + "/.well-known/oauth-protected-resource", authorization=True),
}
for name, code in checks.items():
    print(f"{name}_http={code}")
if checks["unauthenticated_mcp"] != 401:
    raise SystemExit("unauthenticated MCP boundary changed")
if checks["oauth_path_candidate"] != 404 or checks["oauth_root_candidate"] != 404:
    raise SystemExit("OAuth metadata is no longer an all-404 optional-discovery case")
PY

echo "compatibility_override=known_0.0.10_optional_oauth_metadata_false_negative"
echo "EDGE1_TUNNEL_COMPAT_DOCTOR=PASS"
