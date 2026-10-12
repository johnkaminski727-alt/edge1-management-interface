#!/bin/sh
# Install the Edge2 Agent Shell Claude connector (Caddy front end).
#
# OPERATOR-APPROVED FULL ACCESS: this connector exposes the root Edge2 Agent
# Shell (127.0.0.1:8114) to claude.ai behind single-operator OAuth + TOTP,
# Anthropic-only source addresses, a 7-day sign-in and an audit log.
#
#   sudo sh install-edge2-claude-gateway.sh            # dry run (default): checks only
#   sudo sh install-edge2-claude-gateway.sh --apply    # install / update
#   sudo sh install-edge2-claude-gateway.sh --apply --rotate-client-secret
#   sudo sh install-edge2-claude-gateway.sh --apply --rotate-totp
#   sudo sh install-edge2-claude-gateway.sh --disable  # take the connector offline
#
# Secrets are generated on Edge2 and printed once. Only the client secret's
# SHA-256 is stored. Nothing secret is written to the repository.
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
GATEWAY_DIR=/opt/edge2-claude-gateway
DEPLOY=$ROOT/deploy/edge2-claude-gateway
SERVICE=edge2-claude-gateway.service
SERVICE_USER=edge2-claude-gw
UPSTREAM_SERVICE=edge2-agent-shell.service
UPSTREAM_TOKEN_SRC=/etc/edge2-agent-shell/mcp-token
UPSTREAM_PORT=8114
HOSTNAME_PUBLIC=mcp-edge2.ww.cx
EDGE_HOSTNAME=edge2.ww.cx
PORT=8151
ETC_DIR=/etc/edge2-claude-gateway
UNIT=/etc/systemd/system/$SERVICE
CADDYFILE=/etc/caddy/Caddyfile
SITE_BLOCK=$DEPLOY/$HOSTNAME_PUBLIC.caddy
BEGIN_MARK='# BEGIN edge2-claude-gateway'
END_MARK='# END edge2-claude-gateway'
GATEWAY_SRC=server/business159_claude_gateway.py

MODE=dry-run
ROTATE_CLIENT=0
ROTATE_TOTP=0
for arg in "$@"; do
    case "$arg" in
        --apply) MODE=apply ;;
        --disable) MODE=disable ;;
        --rotate-client-secret) ROTATE_CLIENT=1 ;;
        --rotate-totp) ROTATE_TOTP=1 ;;
        *) echo "unknown argument: $arg" >&2; exit 2 ;;
    esac
done

NEW_CLIENT_SECRET=
NEW_TOTP=
fail() {
    echo "FAIL: $*" >&2
    if [ -n "$NEW_CLIENT_SECRET$NEW_TOTP" ]; then
        echo "New credentials were generated before this failure but not shown." >&2
        echo "After fixing the cause, re-run with: --apply --rotate-client-secret --rotate-totp" >&2
    fi
    exit 1
}
ok() { echo "ok:   $*"; }

[ "$(id -u)" -eq 0 ] || fail "run with sudo"

caddy_valid() { # $1 = candidate Caddyfile
    caddy validate --config "$1" --adapter caddyfile >/dev/null 2>&1
}
strip_block() { # remove our managed block from stdin
    awk -v b="$BEGIN_MARK" -v e="$END_MARK" 'index($0,b)==1{skip=1} !skip{print} index($0,e)==1{skip=0}'
}

if [ "$MODE" = disable ]; then
    if [ -d "$ETC_DIR" ]; then : > "$ETC_DIR/disabled"; fi
    if grep -qF "$BEGIN_MARK" "$CADDYFILE"; then
        tmp=$(mktemp)
        strip_block < "$CADDYFILE" > "$tmp"
        if caddy_valid "$tmp"; then
            cp "$CADDYFILE" "$CADDYFILE.pre-edge2-claude-disable-$(date -u +%Y%m%dT%H%M%SZ)"
            cat "$tmp" > "$CADDYFILE"
            systemctl reload caddy
        else
            echo "warning: Caddyfile without the connector block did not validate; left unchanged" >&2
        fi
        rm -f "$tmp"
    fi
    systemctl disable --now "$SERVICE" 2>/dev/null || true
    echo "Claude connector disabled: site block removed, service stopped, kill-switch file present."
    echo "Re-enable later with: sudo sh $0 --apply"
    exit 0
fi

# ---------------------------------------------------------------- preflight
for cmd in python3 systemctl caddy curl getent cmp install ss awk; do
    command -v "$cmd" >/dev/null 2>&1 || fail "missing command: $cmd"
done
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' || fail "Python >= 3.11 required"
systemctl is-active --quiet caddy || fail "caddy is not active"
[ -r "$CADDYFILE" ] || fail "$CADDYFILE missing"
caddy_valid "$CADDYFILE" || fail "existing Caddyfile does not validate; fix that first"
ok "required commands present; Caddy active and its current Caddyfile is valid"

systemctl is-active --quiet "$UPSTREAM_SERVICE" || fail "$UPSTREAM_SERVICE is not active"
[ -r "$UPSTREAM_TOKEN_SRC" ] || fail "Agent Shell token missing: $UPSTREAM_TOKEN_SRC"
curl -fsS --noproxy '*' "http://127.0.0.1:$UPSTREAM_PORT/healthz" >/dev/null 2>&1 || fail "Agent Shell health check failed on 127.0.0.1:$UPSTREAM_PORT"
if ss -ltn | grep -Eq "(0\.0\.0\.0|\*|\[::\]):$UPSTREAM_PORT "; then fail "Agent Shell must be loopback-only"; fi
ok "Edge2 Agent Shell active and loopback-only on 127.0.0.1:$UPSTREAM_PORT"

[ -r "$ROOT/$GATEWAY_SRC" ] || fail "$ROOT/$GATEWAY_SRC missing: run this installer from a checkout that contains the gateway"
[ -r "$SITE_BLOCK" ] || fail "Caddy site block missing: $SITE_BLOCK"
python3 - "$ROOT/$GATEWAY_SRC" <<'PY' || fail "gateway does not compile"
import sys
compile(open(sys.argv[1], encoding='utf-8').read(), sys.argv[1], 'exec')
PY
ok "gateway source in $ROOT (installs to $GATEWAY_DIR)"

if ss -ltn | grep -q "127.0.0.1:$PORT "; then
    systemctl is-active --quiet "$SERVICE" || fail "port $PORT is in use by something else"
fi
if ss -ltn | grep -Eq "(0\.0\.0\.0|\*|\[::\]):$PORT "; then fail "a public listener exists on $PORT"; fi
ok "port $PORT available on loopback"

edge_ip=$(getent ahostsv4 "$EDGE_HOSTNAME" | awk 'NR==1{print $1}')
resolved=$(getent ahostsv4 "$HOSTNAME_PUBLIC" | awk 'NR==1{print $1}')
[ -n "$edge_ip" ] || fail "cannot resolve $EDGE_HOSTNAME"
[ "$resolved" = "$edge_ip" ] || fail "DNS: $HOSTNAME_PUBLIC resolves to '${resolved:-nothing}', expected the same address as $EDGE_HOSTNAME ($edge_ip). Add an A record first."
ok "DNS $HOSTNAME_PUBLIC -> $edge_ip (same as $EDGE_HOSTNAME)"

if grep -q "^$HOSTNAME_PUBLIC" "$CADDYFILE" && ! grep -qF "$BEGIN_MARK" "$CADDYFILE"; then
    fail "$CADDYFILE already defines $HOSTNAME_PUBLIC outside the managed block"
fi
candidate=$(mktemp)
trap 'rm -f "$candidate"' EXIT
{ strip_block < "$CADDYFILE"; echo; cat "$SITE_BLOCK"; } > "$candidate"
caddy_valid "$candidate" || { caddy validate --config "$candidate" --adapter caddyfile || true; fail "Caddyfile with the connector block does not validate"; }
ok "Caddyfile with the connector block validates"

if [ "$MODE" = dry-run ]; then
    echo
    echo "Dry run passed. Nothing was changed."
    echo "Next: sudo sh $0 --apply"
    exit 0
fi

# -------------------------------------------------------------------- apply
rm -f "$ETC_DIR/disabled"
if ! id "$SERVICE_USER" >/dev/null 2>&1; then
    useradd --system --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin "$SERVICE_USER"
fi
install -d -o root -g "$SERVICE_USER" -m 0750 "$ETC_DIR"
if ! cmp -s "$UPSTREAM_TOKEN_SRC" "$ETC_DIR/upstream-token" 2>/dev/null; then
    install -o root -g "$SERVICE_USER" -m 0640 "$UPSTREAM_TOKEN_SRC" "$ETC_DIR/upstream-token"
    ok "Agent Shell token copied for the gateway"
fi

if [ ! -s "$ETC_DIR/client-id" ]; then
    python3 -c 'import secrets; print("edge2-claude-" + secrets.token_hex(6))' > "$ETC_DIR/client-id"
fi
if [ ! -s "$ETC_DIR/client-secret.sha256" ] || [ "$ROTATE_CLIENT" = 1 ]; then
    NEW_CLIENT_SECRET=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
    printf '%s' "$NEW_CLIENT_SECRET" | python3 -c 'import hashlib,sys; print(hashlib.sha256(sys.stdin.read().encode()).hexdigest())' > "$ETC_DIR/client-secret.sha256"
fi
if [ ! -s "$ETC_DIR/totp-secret" ] || [ "$ROTATE_TOTP" = 1 ]; then
    NEW_TOTP=$(python3 -c 'import base64,secrets; print(base64.b32encode(secrets.token_bytes(20)).decode().rstrip("="))')
    printf '%s\n' "$NEW_TOTP" > "$ETC_DIR/totp-secret"
fi
chown root:"$SERVICE_USER" "$ETC_DIR/client-id" "$ETC_DIR/client-secret.sha256" "$ETC_DIR/totp-secret"
chmod 0640 "$ETC_DIR/client-id" "$ETC_DIR/client-secret.sha256" "$ETC_DIR/totp-secret"
if [ -n "$NEW_CLIENT_SECRET$NEW_TOTP" ] && [ -f /var/lib/edge2-claude-gateway/state.json ]; then
    rm -f /var/lib/edge2-claude-gateway/state.json
    echo "Credentials changed: existing Claude tokens revoked."
fi
ok "credentials in $ETC_DIR"

install -d -o root -g root -m 0755 "$GATEWAY_DIR"
install -o root -g root -m 0644 "$ROOT/$GATEWAY_SRC" "$GATEWAY_DIR/business159_claude_gateway.py"
ok "gateway installed to $GATEWAY_DIR"

install -o root -g root -m 0644 "$DEPLOY/edge2-claude-gateway.service" "$UNIT"
systemctl daemon-reload
systemd-analyze verify "$UNIT"
systemctl enable "$SERVICE" >/dev/null 2>&1
systemctl restart "$SERVICE"
i=0
until curl -fsS --noproxy '*' "http://127.0.0.1:$PORT/healthz" >/dev/null 2>&1; do
    i=$((i + 1)); [ "$i" -lt 20 ] || { journalctl -u "$SERVICE" -n 30 --no-pager >&2; fail "gateway did not become healthy"; }
    sleep 0.5
done
ok "gateway service active on 127.0.0.1:$PORT"

backup="$CADDYFILE.pre-edge2-claude-$(date -u +%Y%m%dT%H%M%SZ)"
cp -p "$CADDYFILE" "$backup"
cat "$candidate" > "$CADDYFILE"
if ! systemctl reload caddy; then
    cat "$backup" > "$CADDYFILE"
    systemctl reload caddy || true
    fail "Caddy reload failed; previous Caddyfile restored from $backup"
fi
ok "Caddy site $HOSTNAME_PUBLIC added (backup: $backup)"

# -------------------------------------------------------------- postflight
code() { curl -s --noproxy '*' -o /dev/null -w '%{http_code}' --max-time 15 "$@"; }
i=0
until [ "$(code "https://$HOSTNAME_PUBLIC/.well-known/oauth-authorization-server")" = 200 ]; do
    i=$((i + 1)); [ "$i" -lt 30 ] || fail "OAuth metadata not reachable over HTTPS after 60 s (check: journalctl -u caddy -n 50)"
    sleep 2
done
[ "$(code "https://$HOSTNAME_PUBLIC/mcp")" = 403 ] || fail "/mcp should refuse non-Anthropic addresses (expected 403)"
[ "$(code "https://$HOSTNAME_PUBLIC/anything-else")" = 404 ] || fail "unexpected path should be 404"
[ "$(code "https://$EDGE_HOSTNAME/")" != 000 ] || fail "existing $EDGE_HOSTNAME site stopped answering"
if ss -ltn | grep -Eq "(0\.0\.0\.0|\*|\[::\]):$PORT "; then fail "gateway must not listen publicly"; fi
ok "postflight: HTTPS certificate issued, metadata 200, /mcp 403 from non-Anthropic address, other paths 404, $EDGE_HOSTNAME still answering, loopback only"

echo
echo "=============================================================="
echo " Claude custom connector settings (claude.ai -> Customize ->"
echo " Connectors -> Add custom connector)"
echo "--------------------------------------------------------------"
echo " Name:                 Edge2 Agent Shell"
echo " MCP server URL:       https://$HOSTNAME_PUBLIC/mcp"
echo " Advanced settings -> OAuth Client ID:     $(cat "$ETC_DIR/client-id")"
if [ -n "$NEW_CLIENT_SECRET" ]; then
    echo " Advanced settings -> OAuth Client Secret: $NEW_CLIENT_SECRET"
else
    echo " OAuth Client Secret:  (unchanged; use --rotate-client-secret for a new one)"
fi
if [ -n "$NEW_TOTP" ]; then
    URI="otpauth://totp/WW.CX:Edge2%20Claude%20connector?secret=$NEW_TOTP&issuer=WW.CX&algorithm=SHA1&digits=6&period=30"
    echo "--------------------------------------------------------------"
    echo " Authenticator (Yubico Authenticator -> Add account):"
    echo "   Issuer: WW.CX   Account: Edge2 Claude connector"
    echo "   Secret key: $NEW_TOTP   (TOTP, SHA1, 6 digits, 30 s)"
    if command -v qrencode >/dev/null 2>&1; then
        qrencode -t ANSIUTF8 "$URI"
    else
        echo "   (install 'qrencode' to show a scannable QR code)"
    fi
fi
echo "=============================================================="
echo " These secrets are shown once. Clear your terminal afterwards."
echo " In claude.ai keep this connector's tools on \"Needs approval\" (root access)."
NEW_CLIENT_SECRET=
NEW_TOTP=
