#!/bin/sh
set -eu

MODE=${1:---check}
case "$MODE" in
  --check|--apply) ;;
  *) echo "usage: $0 [--check|--apply]" >&2; exit 2 ;;
esac

[ "$(id -u)" -eq 0 ] || { echo "run as root" >&2; exit 2; }

VHOST=/etc/apache2/sites-available/000-default.conf
ENABLED=/etc/apache2/sites-enabled/000-default.conf
POLICY=/etc/apache2/wwcx-edge1-default-http-front-door.conf
SOURCE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)/wwcx-edge1-default-http-front-door.conf
INCLUDE='    IncludeOptional /etc/apache2/wwcx-edge1-default-http-front-door.conf'

[ -r "$VHOST" ] || { echo "missing $VHOST" >&2; exit 2; }
[ -r "$SOURCE" ] || { echo "missing $SOURCE" >&2; exit 2; }
[ -e "$ENABLED" ] || { echo "missing enabled vhost $ENABLED" >&2; exit 2; }
command -v apache2ctl >/dev/null 2>&1 || { echo "apache2ctl not found" >&2; exit 2; }
command -v python3 >/dev/null 2>&1 || { echo "python3 not found" >&2; exit 2; }

grep -Eq '^[[:space:]]*<VirtualHost[[:space:]]+\*:80>[[:space:]]*$' "$VHOST" || {
  echo "unexpected default vhost: missing <VirtualHost *:80>" >&2
  exit 2
}
grep -Eq '^[[:space:]]*ServerName[[:space:]]+default\.invalid[[:space:]]*$' "$VHOST" || {
  echo "unexpected default vhost: missing ServerName default.invalid" >&2
  exit 2
}
[ "$(readlink -f "$ENABLED")" = "$(readlink -f "$VHOST")" ] || {
  echo "enabled 000-default.conf does not resolve to expected vhost" >&2
  exit 2
}

if [ "$MODE" = --check ]; then
  echo "source_policy=$SOURCE"
  echo "target_policy=$POLICY"
  echo "vhost=$VHOST"
  sha256sum "$VHOST"
  grep -F "$INCLUDE" "$VHOST" >/dev/null 2>&1 && echo "include=present" || echo "include=absent"
  apache2ctl configtest
  exit 0
fi

STAMP=$(date -u +%Y%m%dT%H%M%SZ)
BACKUP=/var/backups/wwcx-edge1-front-door-$STAMP
install -d -m 0700 "$BACKUP"
cp -a "$VHOST" "$BACKUP/000-default.conf.before"
if [ -e "$POLICY" ]; then
  cp -a "$POLICY" "$BACKUP/wwcx-edge1-default-http-front-door.conf.before"
  POLICY_EXISTED=1
else
  POLICY_EXISTED=0
fi

install -o root -g root -m 0644 "$SOURCE" "$POLICY"

python3 - "$VHOST" "$INCLUDE" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
include = sys.argv[2]
text = path.read_text(encoding="utf-8")
if include not in text:
    closings = [i for i in range(len(text)) if text.startswith("</VirtualHost>", i)]
    if len(closings) != 1:
        raise SystemExit(f"expected exactly one VirtualHost closing tag, found {len(closings)}")
    pos = closings[0]
    text = text[:pos] + include + "\n" + text[pos:]
    path.write_text(text, encoding="utf-8")
PY

if ! apache2ctl configtest; then
  cp -a "$BACKUP/000-default.conf.before" "$VHOST"
  if [ "$POLICY_EXISTED" -eq 1 ]; then
    cp -a "$BACKUP/wwcx-edge1-default-http-front-door.conf.before" "$POLICY"
  else
    rm -f "$POLICY"
  fi
  echo "configtest failed; pre-change files restored" >&2
  exit 1
fi

cat > "$BACKUP/rollback.sh" <<EOF
#!/bin/sh
set -eu
cp -a '$BACKUP/000-default.conf.before' '$VHOST'
EOF
if [ "$POLICY_EXISTED" -eq 1 ]; then
  printf "%s\n" "cp -a '$BACKUP/wwcx-edge1-default-http-front-door.conf.before' '$POLICY'" >> "$BACKUP/rollback.sh"
else
  printf "%s\n" "rm -f '$POLICY'" >> "$BACKUP/rollback.sh"
fi
cat >> "$BACKUP/rollback.sh" <<EOF
apache2ctl configtest
systemctl reload apache2
EOF
chmod 0700 "$BACKUP/rollback.sh"

systemctl reload apache2
systemctl is-active --quiet apache2
apache2ctl configtest

sha256sum "$VHOST" "$POLICY" "$BACKUP/000-default.conf.before" > "$BACKUP/SHA256SUMS"
printf 'backup=%s\nrollback=%s\n' "$BACKUP" "$BACKUP/rollback.sh"
