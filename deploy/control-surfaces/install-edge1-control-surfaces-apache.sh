#!/bin/sh
set -eu

MODE=${1:---check}
case "$MODE" in
  --check|--apply) ;;
  *) echo "usage: $0 [--check|--apply]" >&2; exit 2 ;;
esac

[ "$(id -u)" -eq 0 ] || { echo "run as root" >&2; exit 2; }

VHOST=/etc/apache2/sites-available/edge1.ww.cx.conf
POLICY=/etc/apache2/wwcx-edge1-control-surfaces.conf
SOURCE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)/wwcx-edge1-control-surfaces.conf
INCLUDE='    IncludeOptional /etc/apache2/wwcx-edge1-control-surfaces.conf'

[ -r "$VHOST" ] || { echo "missing $VHOST" >&2; exit 2; }
[ -r "$SOURCE" ] || { echo "missing $SOURCE" >&2; exit 2; }
command -v apache2ctl >/dev/null 2>&1 || { echo "apache2ctl not found" >&2; exit 2; }
command -v python3 >/dev/null 2>&1 || { echo "python3 not found" >&2; exit 2; }

if [ "$MODE" = --check ]; then
  echo "source_policy=$SOURCE"
  echo "target_policy=$POLICY"
  echo "vhost=$VHOST"
  grep -F "$INCLUDE" "$VHOST" >/dev/null 2>&1 && echo "include=present" || echo "include=absent"
  apache2ctl configtest
  exit 0
fi

STAMP=$(date -u +%Y%m%dT%H%M%SZ)
BACKUP=/var/backups/wwcx-edge1-control-surfaces-$STAMP
install -d -m 0700 "$BACKUP"
cp -a "$VHOST" "$BACKUP/edge1.ww.cx.conf.before"
if [ -e "$POLICY" ]; then
  cp -a "$POLICY" "$BACKUP/wwcx-edge1-control-surfaces.conf.before"
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
    pos = text.rfind("</VirtualHost>")
    if pos < 0:
        raise SystemExit("final VirtualHost closing tag not found")
    text = text[:pos] + include + "\n" + text[pos:]
    path.write_text(text, encoding="utf-8")
PY

if ! apache2ctl configtest; then
  cp -a "$BACKUP/edge1.ww.cx.conf.before" "$VHOST"
  if [ "$POLICY_EXISTED" -eq 1 ]; then
    cp -a "$BACKUP/wwcx-edge1-control-surfaces.conf.before" "$POLICY"
  else
    rm -f "$POLICY"
  fi
  echo "configtest failed; pre-change files restored" >&2
  exit 1
fi

cat > "$BACKUP/rollback.sh" <<EOF
#!/bin/sh
set -eu
cp -a '$BACKUP/edge1.ww.cx.conf.before' '$VHOST'
EOF
if [ "$POLICY_EXISTED" -eq 1 ]; then
  printf "%s\n" "cp -a '$BACKUP/wwcx-edge1-control-surfaces.conf.before' '$POLICY'" >> "$BACKUP/rollback.sh"
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

sha256sum "$VHOST" "$POLICY" "$BACKUP/edge1.ww.cx.conf.before" > "$BACKUP/SHA256SUMS"
printf 'backup=%s\nrollback=%s\n' "$BACKUP" "$BACKUP/rollback.sh"
