#!/bin/bash
# Mail Room authenticated sending — run as root from a checkout of this branch on edge1.
#
#   sudo deploy/email/mail-room-send/install.sh --apply              Phase 1a: signed send route, Send button.
#                                                                   Identities stay disabled; nothing can send.
#   sudo deploy/email/mail-room-send/install.sh --enable-identities  Phase 1b: authorize every sender identity.
#   sudo deploy/email/mail-room-send/install.sh --update             Roll later overlay changes onto copies of
#                                                                   the running releases (auto-restores on failure).
#   sudo deploy/email/mail-room-send/install.sh --rollback <stamp>   Undo a Phase 1a install (and 1b if done).
#
# New release folders are copies of the running ones; nothing existing is edited in place.
set -euo pipefail

REL=/opt/wwcx-email/releases
GW_OLD=$REL/evidence-gated-local-mta-20261006
MR_OLD=$REL/scg-catchall-mailroom-20261006
GW_D=/etc/systemd/system/wwcx-outbound-mail-gateway.service.d
MR_D=/etc/systemd/system/wwcx-mail-room.service.d
ENVF=/etc/wwcx/mail-send.env
IDS=/etc/wwcx/outbound-mail/identities.json
WWW=/var/www/mail-room
GW_SHA=2da37675e3fbb7f2bf3ea7d30c4b72f6d41acd3c087762e540c58f376dc867c1  # running suppressed server this patch is based on
MR_SHA=58d2e92aa79e9315f51fd7b24a8074052a3675b4144d29ddf2ee5f5398c8889d  # running mail_room_http.py
IA_SHA=cf67e9a36d2c50e29696b38eb83b9ffb385aa180ea0032376af42aafd1549f4e  # running identity_aware_outbound_gateway.py (for --update)
OG_SHA=f1e24d0312e585cb57c5832c24a6298f616980085edb3dd5327ef3238850dadc  # running outbound_mail_gateway.py (for --update)
SRC=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$SRC/../../.." && pwd)

die() { echo "FAIL: $*" >&2; exit 1; }
[ "$(id -u)" = 0 ] || die "run as root"

restart() {  # returns non-zero instead of exiting so callers can roll back
  systemctl daemon-reload
  systemctl restart wwcx-outbound-mail-gateway wwcx-mail-room || true
  sleep 3
  systemctl is-active --quiet wwcx-outbound-mail-gateway || { echo "gateway is not active (journalctl -u wwcx-outbound-mail-gateway)" >&2; return 1; }
  systemctl is-active --quiet wwcx-mail-room || { echo "Mail Room is not active (journalctl -u wwcx-mail-room)" >&2; return 1; }
}

probe() {  # probe <label> <expected gateway error code> <signing: none|prep|send>
  python3 - "$1" "$2" "$3" <<'PY'
import hashlib, hmac, json, os, secrets, sys, time, urllib.error, urllib.request
label, expected, mode = sys.argv[1], sys.argv[2], sys.argv[3]
path = "/outbound-mail/send"
body = json.dumps({"to": ["probe@example.invalid"], "body": "probe"}).encode()  # no subject, no confirm_send: can never send
headers = {"Content-Type": "application/json"}
if mode != "none":
    if mode == "send":
        secret, client = dict(l.split("=", 1) for l in open("/etc/wwcx/mail-send.env").read().split() if "=" in l)["WWCX_MAIL_SEND_TOKEN"], "wwcx-mail-room"
    else:
        pid = os.popen("systemctl show -p MainPID --value wwcx-outbound-mail-gateway").read().strip()
        env = dict(x.split("=", 1) for x in open(f"/proc/{pid}/environ", "rb").read().decode().split("\0") if "=" in x)
        secret, client = env.get("WWCX_MAIL_GATEWAY_TOKEN", "x" * 32), "wwcx-private-ai"
    ts, nonce, digest = str(int(time.time())), secrets.token_urlsafe(24), hashlib.sha256(body).hexdigest()
    canonical = "\n".join(["WWCX-HMAC-SHA256", "POST", path, client, ts, nonce, digest]).encode()
    headers.update({"X-WWCX-Client-ID": client, "X-WWCX-Timestamp": ts, "X-WWCX-Nonce": nonce, "X-WWCX-Content-SHA256": digest,
                    "X-WWCX-Signature": hmac.new(secret.encode(), canonical, hashlib.sha256).hexdigest()})
try:
    with urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8104" + path, data=body, headers=headers, method="POST"), timeout=10) as r:
        code, out = r.status, r.read()
except urllib.error.HTTPError as e:
    code, out = e.code, e.read()
error = json.loads(out or b"{}").get("error")
ok = error == expected and code >= 400
print(("PASS" if ok else "FAIL") + f": {label}: HTTP {code} {error}")
sys.exit(0 if ok else 1)
PY
}

case "${1:-}" in
--apply)
  STAMP=$(date -u +%Y%m%dT%H%M%SZ)
  GW_NEW=$REL/mail-room-send-gateway-$STAMP
  MR_NEW=$REL/mail-room-send-mailroom-$STAMP
  BK=/root/mail-room-send-$STAMP

  # Preflight: refuse if the running releases are not the ones this patch was built from.
  grep -q "$GW_OLD" "$GW_D/90-evidence-gated-local-mta.conf" || die "gateway override no longer points at $GW_OLD"
  grep -q "$MR_OLD" "$MR_D/70-scg-catchall.conf" || die "Mail Room override no longer points at $MR_OLD"
  ls "$GW_D" "$MR_D" | grep -q '^9[5-9]-' && die "an override sorting after 90- already exists; review before installing"
  echo "$GW_SHA  $GW_OLD/server/outbound_mail_gateway_suppressed_server.py" | sha256sum -c --quiet || die "running gateway send handler changed since this patch was written"
  echo "$MR_SHA  $MR_OLD/server/mail_room_http.py" | sha256sum -c --quiet || die "running mail_room_http.py changed since this patch was written"
  python3 -c "import json,sys; sys.exit(json.load(open('$IDS'))['outbound_activation_authorized'] is not False)" || die "identity activation must be off before Phase 1a"

  mkdir -p "$BK"; cp -a "$GW_D" "$MR_D" "$IDS" "$BK/"; cp -a "$WWW" "$BK/www-mail-room"
  cp -a "$GW_OLD" "$GW_NEW"; cp -a "$MR_OLD" "$MR_NEW"
  install -m 0644 "$SRC"/gateway/server/*.py "$GW_NEW/server/"
  install -m 0644 "$SRC"/mailroom/server/*.py "$MR_NEW/server/"
  for f in index.html app.js styles.css; do
    install -m 0644 "$REPO/src/web/mail-room/$f" "$MR_NEW/src/web/mail-room/$f"
    install -m 0644 "$REPO/src/web/mail-room/$f" "$WWW/$f"
  done
  python3 -m py_compile "$GW_NEW"/server/outbound_mail_send_auth.py "$GW_NEW"/server/outbound_mail_gateway_suppressed_server.py "$MR_NEW"/server/mail_room_send.py "$MR_NEW"/server/mail_room_http.py

  if [ ! -s "$ENVF" ]; then
    (umask 077; python3 -c 'import secrets; print("WWCX_MAIL_SEND_TOKEN=" + secrets.token_urlsafe(48))' > "$ENVF")
  fi
  chown root:root "$ENVF"; chmod 600 "$ENVF"

  cat > "$GW_D/95-mail-room-send.conf" <<EOF
# $STAMP: signed send route (deploy/email/mail-room-send). Rollback: install.sh --rollback $STAMP
[Service]
WorkingDirectory=$GW_NEW
ExecStart=
ExecStart=/usr/bin/python3 $GW_NEW/server/outbound_mail_gateway_runtime_server.py --config /etc/wwcx/outbound-mail/gateway.json --identities $IDS --host 127.0.0.1 --port 8104
EnvironmentFile=$ENVF
EOF
  cat > "$MR_D/95-mail-room-send.conf" <<EOF
# $STAMP: Mail Room Send action (deploy/email/mail-room-send). Rollback: install.sh --rollback $STAMP
[Service]
WorkingDirectory=$MR_NEW
ExecStart=
ExecStart=/usr/bin/python3 -B -m server.mail_room_http --database /var/lib/wwcx-mail-room-drafts/drafts.sqlite3
EnvironmentFile=$ENVF
EOF
  failed=0
  restart || failed=1
  if [ $failed = 0 ]; then
    probe "unsigned send is rejected" authentication_failed none || failed=1
    probe "preparation (AVA) token cannot sign sends" authentication_failed prep || failed=1
    probe "signed send passes auth and stops at validation (nothing sent)" invalid_request send || failed=1
  fi
  if [ $failed = 1 ]; then
    echo "Checks failed; rolling back." >&2
    "$0" --rollback "$STAMP"; exit 1
  fi
  echo
  echo "Phase 1a installed ($STAMP). Identities are still disabled, so nothing can send."
  echo "Hard-refresh the Mail Room, confirm it loads and Prepare works, then run: $0 --enable-identities"
  echo "Rollback: $0 --rollback $STAMP"
  ;;

--enable-identities)
  ls "$GW_D"/95-mail-room-send.conf >/dev/null 2>&1 || die "Phase 1a is not installed"
  probe "unsigned send is rejected" authentication_failed none || die "send route is not authenticated; refusing to enable identities"
  STAMP=$(date -u +%Y%m%dT%H%M%SZ); cp -a "$IDS" "/root/identities.json.pre-enable-$STAMP"
  python3 - "$IDS" <<'PY'
import json, sys
path = sys.argv[1]; registry = json.load(open(path))
system = registry["sender_selection"]["system_sender"]
addresses = [p["address"] for p in registry["sender_profiles"].values() if p["address"] != system]
for profile in registry["sender_profiles"].values():
    profile["outbound_enabled"] = profile["address"] != system
registry["sender_selection"]["live_sender_allowlist"] = addresses
registry["outbound_activation_authorized"] = True
with open(path, "w") as handle:  # rewrite in place: keeps owner and mode
    handle.write(json.dumps(registry, indent=2) + "\n")
print("Authorized senders:", ", ".join(addresses))
PY
  restart || { cp -a "/root/identities.json.pre-enable-$STAMP" "$IDS"; restart; die "gateway rejected the identity registry; restored the previous file"; }
  probe "unsigned send is still rejected" authentication_failed none
  echo "Identities enabled. Backup: /root/identities.json.pre-enable-$STAMP"
  echo "creekco.ca and omegafx.com still cannot send until Phase 2 adds them to allowed_from_domains."
  ;;

--update)
  # Roll this branch's overlay onto copies of the currently running 95- releases.
  for d in "$GW_D" "$MR_D"; do [ -f "$d/95-mail-room-send.conf" ] || die "Phase 1a is not installed"; done
  GW_CUR=$(sed -n 's/^WorkingDirectory=//p' "$GW_D/95-mail-room-send.conf")
  MR_CUR=$(sed -n 's/^WorkingDirectory=//p' "$MR_D/95-mail-room-send.conf")
  echo "$IA_SHA  $GW_CUR/server/identity_aware_outbound_gateway.py" | sha256sum -c --quiet || die "running identity_aware_outbound_gateway.py changed since this patch was written"
  echo "$OG_SHA  $GW_CUR/server/outbound_mail_gateway.py" | sha256sum -c --quiet || die "running outbound_mail_gateway.py changed since this patch was written"
  STAMP=$(date -u +%Y%m%dT%H%M%SZ); BK=/root/mail-room-send-update-$STAMP; POLICY=/etc/wwcx/outbound-mail/policy.json
  GW_NEW=$REL/mail-room-send-gateway-$STAMP; MR_NEW=$REL/mail-room-send-mailroom-$STAMP
  mkdir -p "$BK"; cp -a "$GW_D/95-mail-room-send.conf" "$BK/gateway-95.conf"; cp -a "$MR_D/95-mail-room-send.conf" "$BK/mailroom-95.conf"
  cp -a "$POLICY" "$BK/policy.json"; cp -a "$WWW" "$BK/www-mail-room"
  cp -a "$GW_CUR" "$GW_NEW"; cp -a "$MR_CUR" "$MR_NEW"
  install -m 0644 "$SRC"/gateway/server/*.py "$GW_NEW/server/"
  install -m 0644 "$SRC"/mailroom/server/*.py "$MR_NEW/server/"
  for f in index.html app.js styles.css; do
    install -m 0644 "$REPO/src/web/mail-room/$f" "$MR_NEW/src/web/mail-room/$f"; install -m 0644 "$REPO/src/web/mail-room/$f" "$WWW/$f"
  done
  for f in "$SRC"/gateway/server/*.py; do python3 -m py_compile "$GW_NEW/server/$(basename "$f")"; done
  for f in "$SRC"/mailroom/server/*.py; do python3 -m py_compile "$MR_NEW/server/$(basename "$f")"; done
  # The policy keeps its own sender-domain list; align it with the commissioned local-MTA domains.
  python3 - "$POLICY" /etc/wwcx/outbound-mail/gateway.json <<'PY'
import json, sys
policy_path, gateway_path = sys.argv[1:]
policy = json.load(open(policy_path))
wanted = json.load(open(gateway_path))["provider"]["profiles"]["edge1_local_mta"]["allowed_from_domains"]
allowed = policy["delivery"]["allowed_from_domains"]
added = [d for d in wanted if d not in allowed]
allowed.extend(added)
with open(policy_path, "w") as handle:
    handle.write(json.dumps(policy, indent=2) + "\n")
print("policy allowed_from_domains:", allowed, "(added: " + (", ".join(added) or "none") + ")")
PY
  sed -i "s#$GW_CUR#$GW_NEW#g" "$GW_D/95-mail-room-send.conf"; sed -i "s#$MR_CUR#$MR_NEW#g" "$MR_D/95-mail-room-send.conf"
  failed=0
  restart || failed=1
  [ $failed = 0 ] && { probe "unsigned send is rejected" authentication_failed none || failed=1; }
  [ $failed = 0 ] && { probe "signed send passes auth and stops at validation (nothing sent)" invalid_request send || failed=1; }
  if [ $failed = 1 ]; then
    echo "Update failed; restoring the previous releases." >&2
    cp -a "$BK/gateway-95.conf" "$GW_D/95-mail-room-send.conf"; cp -a "$BK/mailroom-95.conf" "$MR_D/95-mail-room-send.conf"
    cp -a "$BK/policy.json" "$POLICY"; cp -a "$BK/www-mail-room/." "$WWW/"
    restart || true; exit 1
  fi
  echo "Updated ($STAMP): gateway $GW_NEW, Mail Room $MR_NEW. Backups in $BK."
  ;;

--rollback)
  STAMP=${2:?usage: $0 --rollback <stamp>}; BK=/root/mail-room-send-$STAMP
  [ -d "$BK" ] || die "no backup at $BK"
  rm -f "$GW_D/95-mail-room-send.conf" "$MR_D/95-mail-room-send.conf"
  cp -a "$BK/identities.json" "$IDS"
  cp -a "$BK/www-mail-room/." "$WWW/"
  restart || die "services did not come back after rollback; check journalctl"
  echo "Rolled back to the pre-$STAMP state. New release folders are left in $REL for inspection."
  ;;

*) sed -n '2,11p' "$0"; exit 2 ;;
esac
