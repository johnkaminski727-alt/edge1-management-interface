#!/usr/bin/env bash
set -euo pipefail

# Approval-gated installer for the VPN-only Private Library Search route.
#
# Route exposure beyond localhost requires explicit operator approval per
# project guardrails. This script therefore:
#   1. refuses to run without the --approve-route-exposure flag,
#   2. additionally requires a typed confirmation phrase (or
#      EDGE1_ROUTE_APPROVAL=I_APPROVE for a deliberate non-interactive run),
#   3. only accepts a private (RFC1918/ULA) bind address, never 0.0.0.0
#      or a public IP,
#   4. requires the operator htpasswd file to exist before installing.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMPLATE="$REPO_ROOT/deploy/nginx/edge1-private-library-search.conf.template"
HTPASSWD_FILE="${EDGE1_SEARCH_HTPASSWD:-/etc/nginx/edge1-search.htpasswd}"
ROUTE_PORT="${EDGE1_ROUTE_PORT:-8443}"
CONF_DST="/etc/nginx/conf.d/edge1-private-library-search.conf"

usage() {
  echo "Usage: $0 --approve-route-exposure --bind-ip <vpn-ip> [--server-name <name>]" >&2
  exit 1
}

APPROVED="no"
BIND_IP=""
SERVER_NAME="edge1-search.internal"

while [ $# -gt 0 ]; do
  case "$1" in
    --approve-route-exposure) APPROVED="yes"; shift ;;
    --bind-ip) BIND_IP="${2:-}"; shift 2 ;;
    --server-name) SERVER_NAME="${2:-}"; shift 2 ;;
    *) usage ;;
  esac
done

if [ "${EUID}" -ne 0 ]; then
  echo "install-private-library-search-route.sh must run as root" >&2
  exit 1
fi

[ "$APPROVED" = "yes" ] || { echo "Refusing: --approve-route-exposure not given." >&2; exit 1; }
[ -n "$BIND_IP" ] || usage

for command in nginx python3; do
  command -v "$command" >/dev/null 2>&1 || { echo "Missing required command: $command" >&2; exit 1; }
done

# The bind address must be a specific private address on this host.
python3 - "$BIND_IP" <<'PY'
import ipaddress, sys
ip = ipaddress.ip_address(sys.argv[1])
if ip.is_unspecified:
    sys.exit("Refusing: bind address must not be 0.0.0.0 / ::")
if ip.is_loopback:
    sys.exit("Refusing: for loopback use the systemd service directly")
if not ip.is_private:
    sys.exit(f"Refusing: {ip} is not a private address; public exposure is not supported")
PY

if ! ip -o addr show 2>/dev/null | grep -qw "$BIND_IP"; then
  echo "Refusing: $BIND_IP is not configured on any local interface" >&2
  exit 1
fi

if [ ! -s "$HTPASSWD_FILE" ]; then
  echo "Refusing: $HTPASSWD_FILE missing or empty." >&2
  echo "Create operator credentials first: sudo deploy/create-search-route-htpasswd.sh" >&2
  exit 1
fi

if [ "${EDGE1_ROUTE_APPROVAL:-}" != "I_APPROVE" ]; then
  echo "About to expose the read-only search UI on ${BIND_IP}:${ROUTE_PORT} (VPN route)."
  read -rp "Type 'expose search route' to confirm: " CONFIRM
  [ "$CONFIRM" = "expose search route" ] || { echo "Confirmation phrase not matched; aborting." >&2; exit 1; }
fi

sed -e "s/__VPN_BIND_IP__/${BIND_IP}/g" \
    -e "s/__ROUTE_PORT__/${ROUTE_PORT}/g" \
    -e "s/__SERVER_NAME__/${SERVER_NAME}/g" \
    "$TEMPLATE" > "$CONF_DST"
chmod 644 "$CONF_DST"

nginx -t
systemctl reload nginx

echo "Installed VPN route: http://${BIND_IP}:${ROUTE_PORT}/ (auth required)"
echo "Next: deploy/private-library-search-route-smoke-test.sh ${BIND_IP} ${ROUTE_PORT}"
