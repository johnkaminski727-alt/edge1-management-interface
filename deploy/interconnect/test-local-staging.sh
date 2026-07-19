#!/bin/sh
set -eu

HOST=${HOST:-127.0.0.1}
PORT=${PORT:-5061}
SERVER_NAME=${SERVER_NAME:-interconnect.ww.cx}

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

command -v openssl >/dev/null 2>&1 || fail "openssl is required"
command -v ss >/dev/null 2>&1 || fail "ss is required"

ss -lnt | grep -E "[.:]${PORT}[[:space:]]" >/dev/null || fail "nothing is listening on TCP ${PORT}"
pass "TCP ${PORT} listener exists"

TLS_OUT=$(mktemp)
trap 'rm -f "$TLS_OUT"' EXIT HUP INT TERM

if ! openssl s_client -connect "${HOST}:${PORT}" -servername "$SERVER_NAME" -verify_return_error </dev/null >"$TLS_OUT" 2>&1; then
  cat "$TLS_OUT" >&2
  fail "TLS handshake or certificate verification failed"
fi

grep -E 'Protocol *: TLSv1\.[23]|New, TLSv1\.[23]' "$TLS_OUT" >/dev/null || fail "TLS 1.2 or newer was not negotiated"
pass "TLS handshake succeeded with TLS 1.2 or newer"

# This script intentionally does not originate an INVITE. SIP method tests
# should use sipsak or a controlled test peer after the loopback listener is up.
echo "Local TLS staging checks completed. No call was placed."
