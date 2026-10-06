#!/bin/sh
set -eu

[ "$(id -u)" -eq 0 ] || { echo "root required" >&2; exit 1; }

BACKUP_ROOT=/var/backups/wwcx-rspamd-pilot-signing
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
mkdir -p "$BACKUP_ROOT/$STAMP"
chmod 0700 "$BACKUP_ROOT" "$BACKUP_ROOT/$STAMP"

for f in dkim_signing.conf worker-proxy.inc; do
  if [ -f "/etc/rspamd/local.d/$f" ]; then
    cp -a "/etc/rspamd/local.d/$f" "$BACKUP_ROOT/$STAMP/$f"
  fi
done

cat > /etc/rspamd/local.d/dkim_signing.conf <<'CFG'
enabled = true;
selector = "edge1-202610";
path = "/var/lib/rspamd/dkim/$domain.$selector.key";
use_domain = "header";
sign_authenticated = true;
sign_local = true;
sign_networks = ["127.0.0.0/8"];
allow_envfrom_empty = true;
try_fallback = false;
CFG

cat > /etc/rspamd/local.d/worker-proxy.inc <<'CFG'
enabled = true;
bind_socket = "127.0.0.1:11332";
milter = yes;
timeout = 60s;
upstream "local" {
  default = yes;
  hosts = "127.0.0.1:11333";
}
count = 1;
max_retries = 1;
discard_on_reject = false;
quarantine_on_reject = false;
spam_header = "X-Spam";
reject_message = "Spam message rejected";
CFG

rspamadm configtest
systemctl restart rspamd
systemctl is-active --quiet rspamd

python3 - <<'PY'
import socket, time
ports=(11332, 11333, 11334)
for attempt in range(30):
    failed=[]
    for port in ports:
        try:
            with socket.socket() as s:
                s.settimeout(1)
                s.connect(("127.0.0.1", port))
        except OSError:
            failed.append(port)
    if not failed:
        break
    time.sleep(0.25)
else:
    raise SystemExit(f"Rspamd listeners did not become ready: {failed}")
PY

[ -z "$(postconf -h smtpd_milters)" ] || { echo "smtpd_milters must remain disabled" >&2; exit 1; }
[ -z "$(postconf -h non_smtpd_milters)" ] || { echo "non_smtpd_milters must remain disabled" >&2; exit 1; }
case "$(postconf -h default_transport)" in
  error:*) ;;
  *) echo "default_transport is not fail-closed" >&2; exit 1 ;;
esac
case "$(postconf -h relay_transport)" in
  error:*) ;;
  *) echo "relay_transport is not fail-closed" >&2; exit 1 ;;
esac

echo "WW.CX Rspamd pilot signing stage applied"
echo "Rspamd proxy: loopback-only on 127.0.0.1:11332"
echo "Postfix milters: disabled"
echo "Outbound transport: disabled"
