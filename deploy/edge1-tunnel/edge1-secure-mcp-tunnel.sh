#!/bin/sh
set -eu

MODE=${1:-run}
TUNNEL_CLIENT=${TUNNEL_CLIENT_BIN:-/usr/local/bin/tunnel-client}
CONFIG=${EDGE1_TUNNEL_CONFIG:-/etc/edge1-tunnel/tunnel-client.yaml}
TUNNEL_ID_FILE=${EDGE1_TUNNEL_ID_FILE:-/etc/edge1-tunnel/tunnel-id}
MCP_TOKEN_FILE=${EDGE1_OPERATOR_MCP_TOKEN_FILE:-/etc/edge1-operator/mcp-token}
API_KEY_FILE=${EDGE1_TUNNEL_API_KEY_FILE:-/etc/edge1-tunnel/runtime-api-key}

case "$MODE" in
    run|doctor) ;;
    *) echo "usage: $0 [run|doctor]" >&2; exit 2 ;;
esac

[ -x "$TUNNEL_CLIENT" ] || { echo "tunnel-client binary unavailable" >&2; exit 10; }
[ -r "$CONFIG" ] || { echo "tunnel-client config unavailable" >&2; exit 11; }
[ -r "$TUNNEL_ID_FILE" ] || { echo "tunnel id file unavailable" >&2; exit 12; }
[ -r "$MCP_TOKEN_FILE" ] || { echo "Edge1 MCP token unavailable" >&2; exit 13; }
[ -r "$API_KEY_FILE" ] || { echo "runtime API key unavailable" >&2; exit 14; }

TUNNEL_ID=$(tr -d '\r\n' < "$TUNNEL_ID_FILE")
MCP_TOKEN=$(tr -d '\r\n' < "$MCP_TOKEN_FILE")

[ "${#TUNNEL_ID}" -eq 39 ] || { echo "invalid tunnel id length" >&2; exit 15; }
case "$TUNNEL_ID" in
    tunnel_*) ;;
    *) echo "invalid tunnel id prefix" >&2; exit 16 ;;
esac
[ "${#MCP_TOKEN}" -ge 32 ] || { echo "invalid local MCP token" >&2; exit 17; }

export CONTROL_PLANE_TUNNEL_ID="$TUNNEL_ID"
export EDGE1_MCP_AUTHORIZATION="Bearer $MCP_TOKEN"
unset TUNNEL_ID MCP_TOKEN

case "$MODE" in
    doctor)
        exec "$TUNNEL_CLIENT" doctor --config "$CONFIG" --explain
        ;;
    run)
        exec "$TUNNEL_CLIENT" run --config "$CONFIG"
        ;;
esac
