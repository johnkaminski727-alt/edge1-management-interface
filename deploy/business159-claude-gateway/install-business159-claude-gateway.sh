#!/bin/sh
# Install the Business159 Claude connector gateway on Edge1 (nginx front end).
#
#   sudo sh install-business159-claude-gateway.sh            # dry run (default): checks only
#   sudo sh install-business159-claude-gateway.sh --apply    # install / update
#   sudo sh install-business159-claude-gateway.sh --apply --rotate-client-secret
#   sudo sh install-business159-claude-gateway.sh --apply --rotate-totp
#   sudo sh install-business159-claude-gateway.sh --disable  # take the connector offline
#   sudo sh install-business159-claude-gateway.sh --apply --full-access  # operator-approved shell + deploys
#   sudo sh install-business159-claude-gateway.sh --apply --read-only    # back to stage 1
#
# Secrets are generated on Edge1 and printed once. Only the client secret's
# SHA-256 is stored. Nothing secret is written to the repository.
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
# The gateway runs from its own directory so the shared engineering checkout
# (/opt/edge1-management-interface, which may be on a working branch with live
# edits) is only read, never updated, by this installer.
GATEWAY_DIR=/opt/business159-claude-gateway
LIVE_SHELL_ENTRY=/opt/edge1-management-interface/tools/mcp/business159-live-shell/src/index.js
DEPLOY=$ROOT/deploy/business159-claude-gateway
SERVICE=business159-claude-gateway.service
SERVICE_USER=business159-operator
HOSTNAME_PUBLIC=mcp-b159.ww.cx
EDGE1_HOSTNAME=edge1.ww.cx
PORT=8150
ETC_DIR=/etc/business159-claude-gateway
UNIT=/etc/systemd/system/$SERVICE
SITE_TEMPLATE=$DEPLOY/$HOSTNAME_PUBLIC.nginx.conf
SITE=/etc/nginx/sites-available/$HOSTNAME_PUBLIC.conf
SITE_LINK=/etc/nginx/sites-enabled/$HOSTNAME_PUBLIC.conf
ACME_ROOT=/var/www/b159-claude-acme
CERT_DIR=/etc/letsencrypt/live/$HOSTNAME_PUBLIC
CHILD=/usr/local/libexec/business159-tunnel/business159-live-shell.sh
GATEWAY_SRC=server/business159_claude_gateway.py

MODE=dry-run
ROTATE_CLIENT=0
ROTATE_TOTP=0
ACCESS=keep
for arg in "$@"; do
    case "$arg" in
        --apply) MODE=apply ;;
        --disable) MODE=disable ;;
        --rotate-client-secret) ROTATE_CLIENT=1 ;;
        --rotate-totp) ROTATE_TOTP=1 ;;
        --full-access) ACCESS=full ;;
        --read-only) ACCESS=read-only ;;
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

nginx_reload_checked() {
    # $1 = file to restore on failure (or empty to remove the site)
    if nginx -t >/dev/null 2>&1; then
        systemctl reload nginx
        return 0
    fi
    nginx -t || true
    if [ -n "$1" ] && [ -f "$1" ]; then
        cp "$1" "$SITE"
    else
        rm -f "$SITE_LINK" "$SITE"
    fi
    nginx -t >/dev/null 2>&1 && systemctl reload nginx || true
    return 1
}

if [ "$MODE" = disable ]; then
    install -d -o root -g "$SERVICE_USER" -m 0750 "$ETC_DIR"
    : > "$ETC_DIR/disabled"
    rm -f "$SITE_LINK"
    nginx -t >/dev/null 2>&1 && systemctl reload nginx || echo "warning: nginx config test failed; reload skipped" >&2
    systemctl disable --now "$SERVICE" 2>/dev/null || true
    echo "Claude connector disabled: site off, service stopped, kill-switch file present."
    echo "Re-enable later with: sudo rm $ETC_DIR/disabled && sudo sh $0 --apply"
    exit 0
fi

# ---------------------------------------------------------------- preflight
for cmd in python3 systemctl nginx certbot curl getent cmp install ss; do
    command -v "$cmd" >/dev/null 2>&1 || fail "missing command: $cmd"
done
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' || fail "Python >= 3.11 required"
systemctl is-active --quiet nginx || fail "nginx is not active"
nginx -t >/dev/null 2>&1 || fail "existing nginx configuration does not pass 'nginx -t'; fix that first"
ok "required commands present; nginx active and its current config is valid"

id "$SERVICE_USER" >/dev/null 2>&1 || fail "$SERVICE_USER account missing (install the Business159 secure MCP tunnel first)"
[ -x "$CHILD" ] || fail "bounded Business159 server wrapper missing: $CHILD"
[ -r /etc/business159-operator/ssh_config ] || fail "Business159 SSH config missing"
[ -r "$LIVE_SHELL_ENTRY" ] || fail "business159-live-shell source missing: $LIVE_SHELL_ENTRY"
ok "bounded business159-live-shell runtime present (shared with the ChatGPT tunnel)"

[ -r "$ROOT/$GATEWAY_SRC" ] || fail "$ROOT/$GATEWAY_SRC missing: run this installer from a checkout that contains the gateway"
[ -r "$SITE_TEMPLATE" ] || fail "nginx site template missing: $SITE_TEMPLATE"
python3 - "$ROOT/$GATEWAY_SRC" <<'PY' || fail "gateway does not compile"
import sys
compile(open(sys.argv[1], encoding='utf-8').read(), sys.argv[1], 'exec')
PY
if [ -r "$GATEWAY_DIR/business159_claude_gateway.py" ] && ! cmp -s "$ROOT/$GATEWAY_SRC" "$GATEWAY_DIR/business159_claude_gateway.py"; then
    echo "note: $GATEWAY_DIR will be updated from $ROOT"
fi
ok "gateway source in $ROOT (installs to $GATEWAY_DIR)"

if ss -ltn | grep -q "127.0.0.1:$PORT "; then
    systemctl is-active --quiet "$SERVICE" || fail "port $PORT is in use by something else"
fi
if ss -ltn | grep -Eq "(0\.0\.0\.0|\*|\[::\]):$PORT "; then fail "a public listener exists on $PORT"; fi
ok "port $PORT available on loopback"

edge1_ip=$(getent ahostsv4 "$EDGE1_HOSTNAME" | awk 'NR==1{print $1}')
resolved=$(getent ahostsv4 "$HOSTNAME_PUBLIC" | awk 'NR==1{print $1}')
[ -n "$edge1_ip" ] || fail "cannot resolve $EDGE1_HOSTNAME"
[ "$resolved" = "$edge1_ip" ] || fail "DNS: $HOSTNAME_PUBLIC resolves to '${resolved:-nothing}', expected the same address as $EDGE1_HOSTNAME ($edge1_ip). Add an A record first."
ok "DNS $HOSTNAME_PUBLIC -> $edge1_ip (same as $EDGE1_HOSTNAME)"

ss -ltn | grep -q " $edge1_ip:443 " || fail "nginx is not bound to $edge1_ip:443 as expected"
ss -ltn | grep -q " $edge1_ip:80 " || fail "nginx is not bound to $edge1_ip:80 as expected"
if [ -e "$SITE" ] && ! grep -q 'b159_claude_gateway' "$SITE"; then fail "$SITE exists and was not created by this installer"; fi
ok "nginx bound to $edge1_ip:80/443; site name free"

if [ "$MODE" = dry-run ]; then
    echo
    echo "Dry run passed. Nothing was changed."
    echo "Next: sudo sh $0 --apply"
    exit 0
fi

# -------------------------------------------------------------------- apply
rm -f "$ETC_DIR/disabled"
install -d -o root -g "$SERVICE_USER" -m 0750 "$ETC_DIR"

if [ ! -s "$ETC_DIR/client-id" ]; then
    python3 -c 'import secrets; print("b159-claude-" + secrets.token_hex(6))' > "$ETC_DIR/client-id"
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
if [ -n "$NEW_CLIENT_SECRET$NEW_TOTP" ] && [ -f /var/lib/business159-claude-gateway/state.json ]; then
    rm -f /var/lib/business159-claude-gateway/state.json
    echo "Credentials changed: existing Claude tokens revoked."
fi
ok "credentials in $ETC_DIR"

install -d -o root -g root -m 0755 "$GATEWAY_DIR"
install -o root -g root -m 0644 "$ROOT/$GATEWAY_SRC" "$GATEWAY_DIR/business159_claude_gateway.py"
ok "gateway installed to $GATEWAY_DIR"

install -o root -g root -m 0644 "$DEPLOY/business159-claude-gateway.service" "$UNIT"
ACCESS_DROPIN=/etc/systemd/system/$SERVICE.d/20-access.conf
case "$ACCESS" in
    full) install -d -m 0755 "$(dirname "$ACCESS_DROPIN")"
          printf '[Service]\nEnvironment=B159_GATEWAY_ACCESS=full\n' > "$ACCESS_DROPIN"
          ok "access: FULL (shell, file changes and deploys); undo with --apply --read-only" ;;
    read-only) rm -f "$ACCESS_DROPIN"; ok "access: read-only (stage 1)" ;;
    keep) [ -f "$ACCESS_DROPIN" ] && ok "access: unchanged (full)" || ok "access: unchanged (read-only)" ;;
esac
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

# nginx, step 1: HTTP-only site (ACME challenge + redirect), unless TLS is already in place.
install -d -o root -g root -m 0755 "$ACME_ROOT"
backup=
if [ -f "$SITE" ]; then backup=$(mktemp); cp "$SITE" "$backup"; fi
render() {
    sed "s/__EDGE1_PUBLIC_IP__/$edge1_ip/g" "$SITE_TEMPLATE"
}
if [ ! -r "$CERT_DIR/fullchain.pem" ]; then
    render | sed '/^# BEGIN-TLS$/,/^# END-TLS$/d' > "$SITE"
    chmod 0644 "$SITE"
    ln -sf "$SITE" "$SITE_LINK"
    nginx_reload_checked "$backup" || fail "nginx rejected the HTTP-only site; it was removed again"
    ok "nginx HTTP site for $HOSTNAME_PUBLIC (ACME challenge only)"
    certbot certonly --webroot -w "$ACME_ROOT" --non-interactive --cert-name "$HOSTNAME_PUBLIC" \
        --key-type ecdsa --deploy-hook 'systemctl reload nginx' -d "$HOSTNAME_PUBLIC" \
        || fail "certbot could not issue $HOSTNAME_PUBLIC (HTTP site left in place; gateway is loopback-only)"
fi
ok "TLS certificate for $HOSTNAME_PUBLIC"

# nginx, step 2: full site.
[ -f "$SITE" ] && { backup=${backup:-$(mktemp)}; cp "$SITE" "$backup"; }
render > "$SITE"
chmod 0644 "$SITE"
ln -sf "$SITE" "$SITE_LINK"
nginx_reload_checked "$backup" || fail "nginx rejected the full site; previous state restored"
rm -f "$backup"
ok "nginx HTTPS site $HOSTNAME_PUBLIC enabled"

# -------------------------------------------------------------- postflight
code() { curl -s --noproxy '*' -o /dev/null -w '%{http_code}' --max-time 15 "$@"; }
sleep 1
[ "$(code "https://$HOSTNAME_PUBLIC/.well-known/oauth-authorization-server")" = 200 ] || fail "OAuth metadata not reachable over HTTPS"
[ "$(code "https://$HOSTNAME_PUBLIC/mcp")" = 403 ] || fail "/mcp should refuse non-Anthropic addresses (expected 403)"
[ "$(code "https://$HOSTNAME_PUBLIC/anything-else")" = 404 ] || fail "unexpected path should be 404"
[ "$(code "https://$EDGE1_HOSTNAME/")" != 000 ] || fail "existing $EDGE1_HOSTNAME site stopped answering"
if ss -ltn | grep -Eq "(0\.0\.0\.0|\*|\[::\]):$PORT "; then fail "gateway must not listen publicly"; fi
ok "postflight: metadata 200, /mcp 403 from non-Anthropic address, other paths 404, $EDGE1_HOSTNAME still answering, loopback only"

echo
echo "=============================================================="
echo " Claude custom connector settings (claude.ai -> Customize ->"
echo " Connectors -> Add custom connector)"
echo "--------------------------------------------------------------"
echo " Name:                 Business159 MCP"
echo " MCP server URL:       https://$HOSTNAME_PUBLIC/mcp"
echo " Advanced settings -> OAuth Client ID:     $(cat "$ETC_DIR/client-id")"
if [ -n "$NEW_CLIENT_SECRET" ]; then
    echo " Advanced settings -> OAuth Client Secret: $NEW_CLIENT_SECRET"
else
    echo " OAuth Client Secret:  (unchanged; use --rotate-client-secret for a new one)"
fi
if [ -n "$NEW_TOTP" ]; then
    URI="otpauth://totp/WW.CX:Business159%20Claude%20connector?secret=$NEW_TOTP&issuer=WW.CX&algorithm=SHA1&digits=6&period=30"
    echo "--------------------------------------------------------------"
    echo " Authenticator (Yubico Authenticator -> Add account):"
    echo "   Issuer: WW.CX   Account: Business159 Claude connector"
    echo "   Secret key: $NEW_TOTP   (TOTP, SHA1, 6 digits, 30 s)"
    if command -v qrencode >/dev/null 2>&1; then
        qrencode -t ANSIUTF8 "$URI"
    else
        echo "   (install 'qrencode' to show a scannable QR code)"
    fi
fi
echo "=============================================================="
echo " These secrets are shown once. Clear your terminal afterwards."
NEW_CLIENT_SECRET=
NEW_TOTP=
