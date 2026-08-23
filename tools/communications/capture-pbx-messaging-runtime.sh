#!/bin/bash
set -euo pipefail
umask 077

EXPECTED_HOST=${EXPECTED_HOST:-edge1.ww.cx}
EVIDENCE_ROOT=${EVIDENCE_ROOT:-/tmp}
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
EVIDENCE_DIR="$EVIDENCE_ROOT/wwcx-pbx-messaging-runtime-$STAMP"
SERVICE=wwcx-messaging-gateway.service
QUARANTINE=/var/lib/wwcx-messaging-gateway/private-mms-quarantine

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

resolve() {
  local name=$1
  shift
  local path
  path=$(command -v "$name" 2>/dev/null || true)
  if [ -n "$path" ]; then
    printf '%s\n' "$path"
    return 0
  fi
  for path in "$@"; do
    if [ -x "$path" ]; then
      printf '%s\n' "$path"
      return 0
    fi
  done
  return 1
}

HOSTNAME_BIN=$(resolve hostname /usr/bin/hostname /bin/hostname || true)
SYSTEMCTL_BIN=$(resolve systemctl /usr/bin/systemctl /bin/systemctl || true)
ASTERISK_BIN=$(resolve asterisk /usr/sbin/asterisk /usr/bin/asterisk || true)
CURL_BIN=$(resolve curl /usr/bin/curl /bin/curl || true)
SS_BIN=$(resolve ss /usr/bin/ss /usr/sbin/ss || true)
PYTHON3_BIN=$(resolve python3 /usr/bin/python3 /bin/python3 || true)
STAT_BIN=$(resolve stat /usr/bin/stat /bin/stat || true)
SHA256_BIN=$(resolve sha256sum /usr/bin/sha256sum /bin/sha256sum || true)
CLAMSCAN_BIN=/usr/bin/clamscan

for pair in \
  "hostname:$HOSTNAME_BIN" \
  "systemctl:$SYSTEMCTL_BIN" \
  "asterisk:$ASTERISK_BIN" \
  "curl:$CURL_BIN" \
  "ss:$SS_BIN" \
  "python3:$PYTHON3_BIN" \
  "stat:$STAT_BIN" \
  "sha256sum:$SHA256_BIN"
do
  name=${pair%%:*}
  path=${pair#*:}
  [ -n "$path" ] && [ -x "$path" ] || fail "$name is unavailable"
done

HOST=$($HOSTNAME_BIN -f 2>/dev/null || $HOSTNAME_BIN)
[ "$HOST" = "$EXPECTED_HOST" ] || fail "expected host $EXPECTED_HOST, got $HOST"

install -d -m 0700 "$EVIDENCE_DIR"

cat > "$EVIDENCE_DIR/README.txt" <<EOF
WW.CX PBX + SMS/MMS read-only runtime evidence
Generated: $STAMP
Host: $HOST

This package contains aggregate service/runtime metadata only.
It deliberately excludes message bodies, telephone numbers, SIP URIs, endpoint names,
credentials, environment values, quarantine file listings, media, calls, and provider traffic.
No service, route, dialplan, carrier, quarantine, firewall, DNS, certificate or authentication
state is changed by this audit.
EOF

$SYSTEMCTL_BIN show "$SERVICE" \
  -p LoadState -p ActiveState -p SubState -p UnitFileState \
  -p User -p Group -p FragmentPath -p WorkingDirectory -p EnvironmentFiles \
  > "$EVIDENCE_DIR/messaging-service-properties.txt"

FRAGMENT=$($SYSTEMCTL_BIN show "$SERVICE" -p FragmentPath --value)
if [ -n "$FRAGMENT" ] && [ -f "$FRAGMENT" ]; then
  $SHA256_BIN "$FRAGMENT" > "$EVIDENCE_DIR/messaging-unit-sha256.txt"
else
  printf 'unit fragment unavailable\n' > "$EVIDENCE_DIR/messaging-unit-sha256.txt"
fi

$SYSTEMCTL_BIN cat "$SERVICE" | "$PYTHON3_BIN" -c '
import re, shlex, sys
sensitive = re.compile(r"(?i)(password|passwd|secret|token|api[_-]?key|private[_-]?key|credential|authorization)")
for raw in sys.stdin:
    line = raw.rstrip("\n")
    stripped = line.lstrip()
    if stripped.startswith("Environment="):
        prefix = line[: len(line) - len(stripped)]
        print(prefix + "Environment=<redacted>")
        continue
    if stripped.startswith("ExecStart="):
        prefix = line[: len(line) - len(stripped)]
        value = stripped[len("ExecStart="):]
        try:
            tokens = shlex.split(value)
        except ValueError:
            print(prefix + "ExecStart=<unparseable-redacted>")
            continue
        out = []
        redact_next = False
        for token in tokens:
            if redact_next:
                out.append("<redacted>")
                redact_next = False
                continue
            if token.startswith("--") and sensitive.search(token):
                if "=" in token:
                    out.append(token.split("=", 1)[0] + "=<redacted>")
                else:
                    out.append(token)
                    redact_next = True
                continue
            if "=" in token and sensitive.search(token.split("=", 1)[0]):
                out.append(token.split("=", 1)[0] + "=<redacted>")
                continue
            out.append(token)
        print(prefix + "ExecStart=" + " ".join(shlex.quote(item) for item in out))
        continue
    print(line)
' > "$EVIDENCE_DIR/messaging-unit-redacted.txt"

$ASTERISK_BIN -rx 'core show version' \
  | head -n 1 > "$EVIDENCE_DIR/asterisk-version.txt"
$ASTERISK_BIN -rx 'core show channels count' \
  | awk '/active channels|active calls|calls processed/ {print}' \
  > "$EVIDENCE_DIR/asterisk-call-counts.txt"

for spec in \
  'endpoints|pjsip show endpoints' \
  'contacts|pjsip show contacts' \
  'registrations|pjsip show registrations' \
  'transports|pjsip show transports'
do
  name=${spec%%|*}
  command=${spec#*|}
  count=$($ASTERISK_BIN -rx "$command" | awk '/Objects found:/ {value=$3} END {print value+0}')
  printf '%s=%s\n' "$name" "$count" >> "$EVIDENCE_DIR/asterisk-pjsip-counts.txt"
done

$SYSTEMCTL_BIN is-active "$SERVICE" > "$EVIDENCE_DIR/messaging-service-active.txt"
$CURL_BIN -fsS --max-time 3 http://127.0.0.1:58080/healthz \
  > "$EVIDENCE_DIR/messaging-health.json"
$CURL_BIN -fsS --max-time 3 http://127.0.0.1:58080/readyz \
  > "$EVIDENCE_DIR/messaging-readiness.json"

if [ -e "$QUARANTINE" ]; then
  $STAT_BIN -c 'path=%n type=%F owner=%U group=%G mode=%a' "$QUARANTINE" \
    > "$EVIDENCE_DIR/mms-quarantine-root.txt"
else
  printf 'path=%s state=absent-or-unobservable\n' "$QUARANTINE" \
    > "$EVIDENCE_DIR/mms-quarantine-root.txt"
fi

if [ -x "$CLAMSCAN_BIN" ]; then
  "$CLAMSCAN_BIN" --version | head -n 1 > "$EVIDENCE_DIR/clamscan-version.txt"
else
  printf 'unavailable\n' > "$EVIDENCE_DIR/clamscan-version.txt"
fi

$SS_BIN -lntup \
  | awk '$4 ~ /:(5060|5061|5038|58080|8088|8089)$/ {print $1, $4}' \
  | LC_ALL=C sort -u \
  > "$EVIDENCE_DIR/relevant-listeners.txt"

(
  cd "$EVIDENCE_DIR"
  find . -type f ! -name SHA256SUMS -print | LC_ALL=C sort \
    | while IFS= read -r file; do $SHA256_BIN "$file"; done \
    > SHA256SUMS
)
chmod -R go-rwx "$EVIDENCE_DIR"

printf '%s\n' "$EVIDENCE_DIR"
