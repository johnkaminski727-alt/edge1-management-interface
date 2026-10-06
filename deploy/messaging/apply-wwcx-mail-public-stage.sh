#!/bin/sh
set -eu
MAIL_IP=89.126.248.191
CERT=/etc/letsencrypt/live/mail.ww.cx/fullchain.pem
KEY=/etc/letsencrypt/live/mail.ww.cx/privkey.pem
[ "${1:-}" = "--apply" ] || { echo "usage: $0 --apply" >&2; exit 2; }
[ -s "$CERT" ] && [ -s "$KEY" ] || { echo "mail.ww.cx TLS certificate missing" >&2; exit 1; }
postconf -e "inet_interfaces=127.0.0.1, $MAIL_IP"
postconf -e "smtpd_tls_cert_file=$CERT"
postconf -e "smtpd_tls_key_file=$KEY"
postconf -e 'smtpd_tls_security_level=may'
# Preserve commissioning protections: public inbound may listen, outbound remains disabled.
[ "$(postconf -h default_transport)" = "error:Outbound delivery disabled during commissioning" ] || { echo "default_transport safety gate changed" >&2; exit 1; }
[ "$(postconf -h relay_transport)" = "error:Outbound relay disabled during commissioning" ] || { echo "relay_transport safety gate changed" >&2; exit 1; }
[ "$(postconf -h smtpd_relay_restrictions)" = "reject_unauth_destination" ] || { echo "relay restriction safety gate changed" >&2; exit 1; }
postfix check
systemctl restart postfix
# UFW can fail in restricted namespaces; host deployment should run this script directly or via systemd-run.
if command -v ufw >/dev/null 2>&1; then
  ufw status 2>/dev/null | grep -F '25/tcp' >/dev/null 2>&1 || ufw allow 25/tcp comment 'WW.CX inbound SMTP canary'
fi
printf '%s\n' 'WW.CX public SMTP stage applied; outbound remains disabled.'
