#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
PLAN="$ROOT/docs/telecom/wwcx-sip-interconnect-staging-plan.md"
DATASET_RUNBOOK="$ROOT/docs/telecom/wwcx-numbering-dataset-operations.md"
MONITORING_RUNBOOK="$ROOT/docs/telecom/wwcx-interconnect-monitoring-and-evidence.md"
CFG="$ROOT/deploy/interconnect/kamailio/kamailio-staging.cfg"
TLS="$ROOT/deploy/interconnect/kamailio/wwcx-tls-staging.cfg.example"
PREFLIGHT="$ROOT/deploy/interconnect/preflight-readonly.sh"
SITE="$ROOT/src/web/interconnect/index.html"
PROFILE="$ROOT/src/web/interconnect/service.json"
PUBLISH="$ROOT/deploy/interconnect/publish-interconnect-site.sh"
APACHE="$ROOT/deploy/interconnect/apache/interconnect.ww.cx.conf.example"
INSTALLER="$ROOT/deploy/interconnect/install-loopback-staging.sh"
NUMBERING="$ROOT/server/wwcx_numbering_node.py"
UNIT="$ROOT/deploy/wwcx-numbering-node.service"
fail() { printf 'validation failed: %s\n' "$1" >&2; exit 1; }
require_file() { test -s "$1" || fail "missing or empty file: $1"; }
require_text() { grep -F "$1" "$2" >/dev/null || fail "expected text not found in $2: $1"; }
for file in "$PLAN" "$DATASET_RUNBOOK" "$MONITORING_RUNBOOK" "$CFG" "$TLS" "$PREFLIGHT" "$SITE" "$PROFILE" "$PUBLISH" "$APACHE" "$INSTALLER" "$NUMBERING" "$UNIT"; do require_file "$file"; done
require_text 'listen=tls:127.0.0.1:5061' "$CFG"
require_text 'Public Registration Disabled' "$CFG"
require_text 'Interconnect Not Yet Activated' "$CFG"
require_text 'public_activation": false' "$PROFILE"
require_text 'Staging' "$SITE"
require_text 'No Apache configuration, certificate, DNS, firewall, or SIP listener was changed.' "$PUBLISH"
require_text '127.0.0.1' "$UNIT"
require_text '8093' "$UNIT"
require_text 'LOOPBACK-ONLY' "$INSTALLER"
require_text 'Atomic source replacement' "$DATASET_RUNBOOK"
require_text 'Controlled source removal' "$DATASET_RUNBOOK"
require_text 'Verify source licensing and redistribution terms' "$DATASET_RUNBOOK"
require_text 'Evidence bundle minimum' "$MONITORING_RUNBOOK"
require_text 'Loopback-only Kamailio staging gate' "$MONITORING_RUNBOOK"
require_text 'No production activation' "$MONITORING_RUNBOOK"
if grep -R -E -- 'BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY|password[[:space:]]*=|secret[[:space:]]*=' "$ROOT/deploy/interconnect" "$ROOT/docs/telecom" "$ROOT/src/web/interconnect" >/dev/null 2>&1; then fail 'possible secret or private key material detected'; fi
python3 -m json.tool "$PROFILE" >/dev/null || fail 'service.json is invalid JSON'
python3 - <<'PY' "$NUMBERING" || fail 'numbering node Python syntax check failed'
import ast
import sys
with open(sys.argv[1], encoding='utf-8') as handle:
    ast.parse(handle.read(), filename=sys.argv[1])
PY
sh -n "$PREFLIGHT" || fail 'preflight shell syntax check failed'
sh -n "$PUBLISH" || fail 'publish shell syntax check failed'
sh -n "$INSTALLER" || fail 'installer shell syntax check failed'
sh -n "$ROOT/deploy/interconnect/validate-staging-assets.sh" || fail 'validator shell syntax check failed'
printf '%s\n' 'WW.CX SIP interconnect staging asset validation passed'
