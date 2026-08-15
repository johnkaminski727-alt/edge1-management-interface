#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PYTHON_BIN=${WWCX_TIME_AUTHORITY_PYTHON:-python3}

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

systemctl is-active --quiet chrony.service || fail "chrony.service is not active"

LISTENER=$(ss -H -ltnp 'sport = :4460' 2>/dev/null || true)
[ -n "$LISTENER" ] || fail "no TCP/4460 listener is present"
printf '%s\n' "$LISTENER" | grep -q 'chronyd' || fail "TCP/4460 is not owned by chronyd"

"$PYTHON_BIN" - <<'PY'
import socket
import ssl
import sys
import time

context = ssl.create_default_context()
context.check_hostname = True
context.verify_mode = ssl.CERT_REQUIRED
context.set_alpn_protocols(["ntske/1"])
started = time.monotonic()
with socket.create_connection(("127.0.0.1", 4460), timeout=5.0) as raw:
    with context.wrap_socket(raw, server_hostname="ntp.ww.cx") as tls:
        if tls.selected_alpn_protocol() != "ntske/1":
            raise SystemExit("NTS-KE ALPN ntske/1 was not negotiated")
        peer = tls.getpeername()
        elapsed = (time.monotonic() - started) * 1000.0
        print("NTS-KE TLS verified: host=ntp.ww.cx peer={}:{} alpn=ntske/1 handshake_ms={:.3f}".format(peer[0], peer[1], elapsed))
PY

chronyc tracking
sh "$ROOT/deploy/time-authority-ntp-server-edge1-smoke-test.sh"

echo "WW.CX Edge1 NTS local smoke test passed."
