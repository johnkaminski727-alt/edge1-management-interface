#!/bin/sh
set -eu

MODE=${1:-run}
TUNNEL_CLIENT=${TUNNEL_CLIENT_BIN:-/usr/local/bin/tunnel-client}
CONFIG=${BUSINESS159_TUNNEL_CONFIG:-/etc/business159-tunnel/tunnel-client.yaml}
TUNNEL_ID_FILE=${BUSINESS159_TUNNEL_ID_FILE:-/etc/business159-tunnel/tunnel-id}
API_KEY_FILE=${BUSINESS159_TUNNEL_API_KEY_FILE:-/etc/business159-tunnel/runtime-api-key}

case "$MODE" in
    run|doctor) ;;
    *) echo "usage: $0 [run|doctor]" >&2; exit 2 ;;
esac

[ -x "$TUNNEL_CLIENT" ] || { echo "tunnel-client binary unavailable" >&2; exit 10; }
[ -r "$CONFIG" ] || { echo "tunnel-client config unavailable" >&2; exit 11; }
[ -r "$TUNNEL_ID_FILE" ] || { echo "Business159 tunnel id unavailable" >&2; exit 12; }
[ -r "$API_KEY_FILE" ] || { echo "Business159 runtime API key unavailable" >&2; exit 13; }

TUNNEL_ID=$(tr -d '\r\n' < "$TUNNEL_ID_FILE")
[ "${#TUNNEL_ID}" -eq 39 ] || { echo "invalid tunnel id length" >&2; exit 14; }
case "$TUNNEL_ID" in
    tunnel_*) ;;
    *) echo "invalid tunnel id prefix" >&2; exit 15 ;;
esac

export CONTROL_PLANE_TUNNEL_ID="$TUNNEL_ID"
unset TUNNEL_ID

case "$MODE" in
    doctor)
        exec "$TUNNEL_CLIENT" doctor --config "$CONFIG" --explain
        ;;
    run)
        exec "$TUNNEL_CLIENT" run --config "$CONFIG"
        ;;
esac
