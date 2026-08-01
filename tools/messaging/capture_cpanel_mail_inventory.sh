#!/bin/sh
# Capture read-only cPanel mail configuration evidence.
#
# This script only invokes cPanel UAPI list/read operations. It does not create,
# edit, delete, suspend, route, or forward mail. Output contains restricted
# operational metadata and must not be committed to Git.

set -eu

usage() {
  cat <<'EOF'
Usage:
  capture_cpanel_mail_inventory.sh --output DIR --user CPANEL_USER \
    [--domain DOMAIN ...]

Default domains when --domain is omitted:
  creekco.ca scgardens.ca omegafx.com

The output directory must be outside a Git working tree.
EOF
}

OUTPUT_DIR=
CPANEL_USER=
DOMAINS=

while [ "$#" -gt 0 ]; do
  case "$1" in
    --output)
      [ "$#" -ge 2 ] || { usage >&2; exit 64; }
      OUTPUT_DIR=$2
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
[ -n "$CPANEL_USER" ] || { echo "--user is required" >&2; exit 64; }
[ -n "$DOMAINS" ] || DOMAINS="creekco.ca scgardens.ca omegafx.com"

command -v uapi >/dev/null 2>&1 || { echo "uapi is required" >&2; exit 69; }
command -v python3 >/dev/null 2>&1 || { echo "python3 is required" >&2; exit 69; }
command -v sha256sum >/dev/null 2>&1 || { echo "sha256sum is required" >&2; exit 69; }

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

validate_uapi_json() {
  python3 - "$1" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
value = json.loads(path.read_text(encoding="utf-8"))
result = value.get("result")
if not isinstance(result, dict) or result.get("status") != 1:
    raise SystemExit("cPanel UAPI response did not report success: %s" % path)
PY
}

capture() {
  name=$1
  shift
  final="$OUTPUT_DIR/$name.json"
  temporary="$final.tmp"
  rm -f "$temporary"
  uapi --output=jsonpretty "--user=$CPANEL_USER" "$@" >"$temporary"
  chmod 0600 "$temporary"
  validate_uapi_json "$temporary"
  mv "$temporary" "$final"
}

capture list-mail-domains Email list_mail_domains
capture list-pops Email list_pops skip_main=1
capture list-domain-forwarders Email list_domain_forwarders
capture list-filters Email list_filters

for domain in $DOMAINS; do
  safe_domain=$(printf '%s' "$domain" | tr '.' '_')
  capture "list-forwarders-$safe_domain" Email list_forwarders "domain=$domain"
  capture "list-default-address-$safe_domain" Email list_default_address \
    "user=$CPANEL_USER" "domain=$domain"
  capture "list-auto-responders-$safe_domain" Email list_auto_responders \
    "domain=$domain"
done

CAPTURED_AT=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
USER_HASH=$(printf '%s' "$CPANEL_USER" | sha256sum | awk '{print $1}')
DOMAINS_JSON=$(printf '%s\n' $DOMAINS | python3 -c \
  'import json,sys; print(json.dumps([line.strip() for line in sys.stdin if line.strip()]))')

python3 - "$OUTPUT_DIR/metadata.json" "$CAPTURED_AT" "$USER_HASH" "$DOMAINS_JSON" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
value = {
    "contract": "wwcx.cpanel-mail-inventory-evidence.v1",
    "captured_at": sys.argv[2],
    "read_only": True,
    "cpanel_user_sha256": sys.argv[3],
    "domains": json.loads(sys.argv[4]),
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

cat <<EOF
Read-only cPanel mail inventory captured.
Evidence directory: $OUTPUT_DIR
Files: $(find "$OUTPUT_DIR" -maxdepth 1 -type f | wc -l | tr -d ' ')
Sensitivity: restricted operational metadata
Next step: normalize the evidence into wwcx.provider-mail-objects.v1 and run reconciliation.
EOF
