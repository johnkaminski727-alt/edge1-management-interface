#!/bin/sh
set -eu

NODE=${BUSINESS159_NODE_BIN:-/usr/bin/node}
MCP_ROOT=${BUSINESS159_MCP_ROOT:-/opt/edge1-management-interface/tools/mcp/business159-live-shell}
ENTRY=${BUSINESS159_MCP_ENTRY:-$MCP_ROOT/src/index.js}
SSH_CONFIG=${BUSINESS159_SSH_CONFIG:-/etc/business159-operator/ssh_config}
KNOWN_HOSTS=${BUSINESS159_KNOWN_HOSTS:-/etc/business159-operator/known_hosts}

[ -x "$NODE" ] || { echo "node runtime unavailable" >&2; exit 20; }
[ -r "$ENTRY" ] || { echo "business159-live-shell entrypoint unavailable" >&2; exit 21; }
[ -r "$MCP_ROOT/package.json" ] || { echo "business159-live-shell package metadata unavailable" >&2; exit 22; }
[ -r "$SSH_CONFIG" ] || { echo "Business159 SSH config unavailable" >&2; exit 23; }
[ -r "$KNOWN_HOSTS" ] || { echo "Business159 known_hosts unavailable" >&2; exit 24; }

export BUSINESS159_SSH_ALIAS=${BUSINESS159_SSH_ALIAS:-business159}
export BUSINESS159_EXPECTED_HOST=${BUSINESS159_EXPECTED_HOST:-business159.web-hosting.com}
export BUSINESS159_EXPECTED_PRINCIPAL=${BUSINESS159_EXPECTED_PRINCIPAL:-wwcxjywl}
export GIT_CONFIG_NOSYSTEM=1
export GIT_TERMINAL_PROMPT=0
export HOME=${BUSINESS159_OPERATOR_HOME:-/var/lib/business159-operator}
export SSH_AUTH_SOCK=${SSH_AUTH_SOCK:-}
export BUSINESS159_SSH_ALIAS
export PATH=/usr/local/libexec/business159-tunnel:/usr/local/bin:/usr/bin:/bin

exec "$NODE" "$ENTRY"
