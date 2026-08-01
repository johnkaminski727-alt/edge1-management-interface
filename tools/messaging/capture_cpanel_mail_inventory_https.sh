#!/bin/sh
# Capture read-only cPanel mail configuration evidence over HTTPS UAPI.
#
# This fallback is intended for jailed shared-hosting shells where the `uapi`
# wrapper is visible but its /usr/local/cpanel/cpanel backend is unavailable.
# It only calls cPanel UAPI list/read operations. The API token is obtained from
# a hidden terminal prompt by default and is never written to the evidence set.

set -eu

usage() {
  cat <<'USAGE'
Usage:
  capture_cpanel_mail_inventory_https.sh --output DIR [--host HOST] \
    [--user CPANEL_USER] [--domain DOMAIN ...]

Defaults:
  --host    current fully-qualified hostname
  --user    current account user
  --domain  creekco.ca scgardens.ca omegafx.com

Authentication:
  The script prompts for a cPanel API token with terminal echo disabled.
  For non-interactive tests only, CPANEL_API_TOKEN may be supplied in the
  environment; it is immediately removed before curl is executed.

The output directory must be outside a Git working tree.
USAGE
}

OUTPUT_DIR=
CPANEL_HOST=
CPANEL_USER=
DOMAINS=

while [ "$#" -gt 0 ]; do
  case "$1" in
    --output)
      [ "$#" -ge 2 ] || { usage >&2; exit 64; }
      OUTPUT_DIR=$2
      shift 2
      ;;
    --host)
      [ "$#" -ge 2 ] || { usage >&2; exit 64; }
      CPANEL_HOST=$2
      shift 2
      ;;
    --user)
      [ "$#" -ge 2 ] || { usage >&2; exit 64; }
      CPANEL_USER=$2
      shift 2
      ;;
    --domain)
      [ "$#" -ge 2 ] || { usage >&2; exit 64; }
      DOMAINS="${DOMAINS}${DOMAINS:+ }$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 64
      ;;
  esac
done

[ -n "$OUTPUT_DIR" ] || { echo "--output is required" >&2; exit 64; }
[ -n "$CPANEL_HOST" ] || CPANEL_HOST=$(hostname -f 2>/dev/null || hostname)
[ -n "$CPANEL_USER" ] || CPANEL_USER=$(id -un)
[ -n "$DOMAINS" ] || DOMAINS="creekco.ca scgardens.ca omegafx.com"

case "$-" in
  *x*)
    echo "Refusing to read an API token while shell tracing is enabled; run 'set +x' first." >&2
    exit 78
    ;;
esac

command -v curl >/dev/null 2>&1 || { echo "curl is required" >&2; exit 69; }
command -v python3 >/dev/null 2>&1 || { echo "python3 is required" >&2; exit 69; }
command -v sha256sum >/dev/null 2>&1 || { echo "sha256sum is required" >&2; exit 69; }

case "$CPANEL_HOST" in
  *[!A-Za-z0-9.-]*|.*|*..*|*.)
    echo "Invalid cPanel host: $CPANEL_HOST" >&2
    exit 64
    ;;
  *.*) ;;
  *)
    echo "cPanel host must be a fully-qualified hostname: $CPANEL_HOST" >&2
    exit 64
    ;;
esac

case "$CPANEL_USER" in
  *[!A-Za-z0-9_-]*|'')
    echo "Invalid cPanel username" >&2
    exit 64
    ;;
esac

for domain in $DOMAINS; do
  case "$domain" in
    *[!a-z0-9.-]*|.*|*..*|*.)
      echo "Invalid normalized domain: $domain" >&2
      exit 64
      ;;
    *.*) ;;
    *)
      echo "Invalid domain: $domain" >&2
      exit 64
      ;;
  esac
done

mkdir -p "$OUTPUT_DIR"
OUTPUT_DIR=$(cd "$OUTPUT_DIR" && pwd -P)

if command -v git >/dev/null 2>&1; then
  GIT_ROOT=$(git -C "$OUTPUT_DIR" rev-parse --show-toplevel 2>/dev/null || true)
  if [ -n "$GIT_ROOT" ]; then
    echo "Refusing to store provider evidence inside Git working tree: $GIT_ROOT" >&2
    exit 73
  fi
fi

chmod 0700 "$OUTPUT_DIR"

TOKEN_SOURCE=environment
CPANEL_TOKEN=${CPANEL_API_TOKEN:-}
unset CPANEL_API_TOKEN 2>/dev/null || true

TTY_STATE=
restore_tty() {
  if [ -n "$TTY_STATE" ] && [ -r /dev/tty ]; then
    stty "$TTY_STATE" < /dev/tty 2>/dev/null || true
  fi
}
cleanup() {
  restore_tty
  CPANEL_TOKEN=
  unset CPANEL_TOKEN 2>/dev/null || true
}
trap cleanup 0 HUP INT TERM

if [ -z "$CPANEL_TOKEN" ]; then
  TOKEN_SOURCE=hidden-terminal-prompt
  [ -r /dev/tty ] || {
    echo "No interactive terminal is available for the API-token prompt." >&2
    exit 77
  }
  TTY_STATE=$(stty -g < /dev/tty) || {
    echo "Unable to read terminal state for hidden API-token input." >&2
    exit 77
  }
  printf 'cPanel API token for %s: ' "$CPANEL_USER" > /dev/tty
  stty -echo < /dev/tty
  IFS= read -r CPANEL_TOKEN < /dev/tty || {
    restore_tty
    printf '\n' > /dev/tty
    echo "Unable to read cPanel API token." >&2
    exit 77
  }
  restore_tty
  TTY_STATE=
  printf '\n' > /dev/tty
fi

case "$CPANEL_TOKEN" in
  *[!A-Za-z0-9_-]*|'')
    echo "Invalid cPanel API-token format" >&2
    exit 64
    ;;
esac

validate_uapi_json() {
  python3 - "$1" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
value = json.loads(path.read_text(encoding="utf-8"))
result = value.get("result")
if not isinstance(result, dict) or result.get("status") != 1:
    errors = result.get("errors") if isinstance(result, dict) else None
    raise SystemExit(
        "cPanel HTTPS UAPI response did not report success: %s errors=%r"
        % (path, errors)
    )
PY
}

run_uapi_https() {
  module=$1
  function=$2
  query=${3:-}
  url="https://$CPANEL_HOST:2083/execute/$module/$function"
  if [ -n "$query" ]; then
    url="$url?$query"
  fi

  # Feed authentication to curl through standard input so the token does not
  # appear in shell history or the curl process command line.
  {
    printf '%s\n' 'silent'
    printf '%s\n' 'show-error'
    printf '%s\n' 'fail'
    printf '%s\n' 'connect-timeout = 10'
    printf '%s\n' 'max-time = 45'
    printf 'header = "Authorization: cpanel %s:%s"\n' "$CPANEL_USER" "$CPANEL_TOKEN"
    printf 'url = "%s"\n' "$url"
  } | curl --config -
}

capture() {
  name=$1
  module=$2
  function=$3
  query=${4:-}
  final="$OUTPUT_DIR/$name.json"
  temporary="$final.tmp"
  rm -f "$temporary"
  if ! run_uapi_https "$module" "$function" "$query" > "$temporary"; then
    rm -f "$temporary"
    return 1
  fi
  chmod 0600 "$temporary"
  validate_uapi_json "$temporary"
  mv "$temporary" "$final"
}

capture list-mail-domains Email list_mail_domains
capture list-pops Email list_pops 'skip_main=1'
capture list-domain-forwarders Email list_domain_forwarders
capture list-filters Email list_filters

for domain in $DOMAINS; do
  safe_domain=$(printf '%s' "$domain" | tr '.' '_')
  capture "list-forwarders-$safe_domain" Email list_forwarders "domain=$domain"
  capture "list-default-address-$safe_domain" Email list_default_address \
    "user=$CPANEL_USER&domain=$domain"
  capture "list-auto-responders-$safe_domain" Email list_auto_responders \
    "domain=$domain"
done

CAPTURED_AT=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
USER_HASH=$(printf '%s' "$CPANEL_USER" | sha256sum | awk '{print $1}')
HOST_HASH=$(printf '%s' "$CPANEL_HOST" | sha256sum | awk '{print $1}')
DOMAINS_JSON=$(printf '%s\n' $DOMAINS | python3 -c \
  'import json,sys; print(json.dumps([line.strip() for line in sys.stdin if line.strip()]))')

python3 - "$OUTPUT_DIR/metadata.json" "$CAPTURED_AT" "$USER_HASH" \
  "$HOST_HASH" "$DOMAINS_JSON" "$TOKEN_SOURCE" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
value = {
    "contract": "wwcx.cpanel-mail-inventory-evidence.v1",
    "captured_at": sys.argv[2],
    "read_only": True,
    "cpanel_user_sha256": sys.argv[3],
    "cpanel_host_sha256": sys.argv[4],
    "domains": json.loads(sys.argv[5]),
    "uapi_execution_mode": "https-api-token",
    "token_input_mode": sys.argv[6],
    "token_retained": False,
    "sensitivity": "restricted-operational-metadata",
}
path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
path.chmod(0o600)
PY

(
  cd "$OUTPUT_DIR"
  sha256sum ./*.json > SHA256SUMS
  chmod 0600 SHA256SUMS
)

CPANEL_TOKEN=
unset CPANEL_TOKEN 2>/dev/null || true

cat <<EOF
Read-only cPanel mail inventory captured over HTTPS UAPI.
Evidence directory: $OUTPUT_DIR
JSON files: $(find "$OUTPUT_DIR" -maxdepth 1 -type f -name '*.json' | wc -l | tr -d ' ')
UAPI execution mode: https-api-token
Token retained: no
Sensitivity: restricted operational metadata
Next step: normalize the evidence into wwcx.provider-mail-objects.v1 and run reconciliation.
EOF
