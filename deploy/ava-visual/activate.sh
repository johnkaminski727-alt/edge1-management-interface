#!/bin/sh
set -eu

REPO=/opt/edge1-management-interface
REF=origin/main
QUEUE_ENV=''
DRY_RUN=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --repo) REPO="$2"; shift 2 ;;
    --ref) REF="$2"; shift 2 ;;
    --queue-env) QUEUE_ENV="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

ROOT=/opt/wwcx/ava-visual
UNIT=/etc/systemd/system/ava-visual-worker.service
DROPIN_DIR=/etc/systemd/system/ava-visual-worker.service.d
DROPIN="$DROPIN_DIR/queue-env.conf"
EVIDENCE_ROOT=/var/lib/wwcx-deployment-evidence/ava-visual
BACKUP_ROOT=/var/backups/wwcx-ava-visual
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
SOURCE_FILES='ava_visual_worker.py ava_visual_generator.py private_ai_browser_worker.py ava_agent_controller.py'

if [ ! -d "$REPO/.git" ] && [ ! -f "$REPO/.git" ]; then echo "repository unavailable: $REPO" >&2; exit 1; fi
git -C "$REPO" cat-file -e "$REF^{commit}"
COMMIT=$(git -C "$REPO" rev-parse "$REF^{commit}")
for name in $SOURCE_FILES; do git -C "$REPO" cat-file -e "$REF:server/$name"; done
git -C "$REPO" cat-file -e "$REF:deploy/ava-visual-worker.service"

if [ "$DRY_RUN" = 1 ]; then
  printf 'mode=dry-run\nrepo=%s\nref=%s\ncommit=%s\nruntime_root=%s\nunit=%s\n' "$REPO" "$REF" "$COMMIT" "$ROOT" "$UNIT"
  exit 0
fi

[ "$(id -u)" -eq 0 ] || { echo "activation must run as root" >&2; exit 1; }
HOST=$(hostname -f 2>/dev/null || hostname)
[ "$HOST" = edge1.ww.cx ] || { echo "refusing activation on non-Edge1 host" >&2; exit 1; }
getent passwd bigbird-ai >/dev/null
getent group bigbird-ai >/dev/null
[ -r /etc/bigbird-ai-gateway.env ] || { echo "Private AI gateway environment is unavailable" >&2; exit 1; }
grep -q '^OPENAI_API_KEY=' /etc/bigbird-ai-gateway.env || { echo "OPENAI_API_KEY is not configured in the gateway environment" >&2; exit 1; }

if [ -z "$QUEUE_ENV" ]; then
  POLLER_ENV=$(systemctl cat bigbird-ai-poller.service 2>/dev/null | sed -n -E 's/^[[:space:]]*EnvironmentFile=-?"?([^"[:space:]]+)"?.*/\1/p' || true)
  for candidate in /etc/wwcx/private-ai-browser-worker.env /etc/wwcx/bigbird-ai-poller.env /etc/bigbird-ai-poller.env $POLLER_ENV; do
    printf '%s\n' "$candidate" | grep -Eq '^/[A-Za-z0-9_./-]+$' || continue
    [ -r "$candidate" ] || continue
    if grep -q '^BB_BROWSER_WORKER_SECRET=' "$candidate" && grep -q '^BB_BROWSER_WORKER_KEY_ID=' "$candidate"; then QUEUE_ENV="$candidate"; break; fi
  done
fi
printf '%s\n' "$QUEUE_ENV" | grep -Eq '^/[A-Za-z0-9_./-]+$' || { echo "no safe reusable queue environment path was identified" >&2; exit 1; }
[ -r "$QUEUE_ENV" ] || { echo "queue worker environment is unavailable" >&2; exit 1; }
grep -q '^BB_BROWSER_WORKER_SECRET=' "$QUEUE_ENV" || { echo "queue signing secret is not configured" >&2; exit 1; }
grep -q '^BB_BROWSER_WORKER_KEY_ID=' "$QUEUE_ENV" || { echo "queue key id is not configured" >&2; exit 1; }

EVIDENCE="$EVIDENCE_ROOT/$STAMP"
BACKUP="$BACKUP_ROOT/$STAMP"
STAGING="$ROOT/releases/.staging-$STAMP"
RELEASE="$ROOT/releases/$COMMIT"
mkdir -p "$EVIDENCE" "$BACKUP" "$ROOT/releases"
chmod 0750 "$EVIDENCE" "$BACKUP"
chmod 0755 "$ROOT" "$ROOT/releases"
mkdir "$STAGING"
trap 'rm -rf "$STAGING"' 0

for name in $SOURCE_FILES; do git -C "$REPO" show "$REF:server/$name" > "$STAGING/$name"; done
git -C "$REPO" show "$REF:deploy/ava-visual-worker.service" > "$STAGING/ava-visual-worker.service"
printf '%s\n' "$COMMIT" > "$STAGING/SOURCE_COMMIT"
chmod 0644 "$STAGING"/*.py "$STAGING/ava-visual-worker.service" "$STAGING/SOURCE_COMMIT"
python3 -m py_compile "$STAGING"/*.py
systemd-analyze verify "$STAGING/ava-visual-worker.service"

PREV_CURRENT=''
if [ -L "$ROOT/current" ]; then PREV_CURRENT=$(readlink -f "$ROOT/current" || true); fi
PREV_UNIT=0; PREV_DROPIN=0; PREV_ACTIVE=0; PREV_ENABLED=0
if [ -f "$UNIT" ]; then cp -a "$UNIT" "$BACKUP/ava-visual-worker.service"; PREV_UNIT=1; fi
if [ -f "$DROPIN" ]; then cp -a "$DROPIN" "$BACKUP/queue-env.conf"; PREV_DROPIN=1; fi
if systemctl is-active --quiet ava-visual-worker.service 2>/dev/null; then PREV_ACTIVE=1; fi
if systemctl is-enabled --quiet ava-visual-worker.service 2>/dev/null; then PREV_ENABLED=1; fi

if [ -e "$RELEASE" ]; then
  for name in $SOURCE_FILES SOURCE_COMMIT; do
    cmp -s "$STAGING/$name" "$RELEASE/$name" || { echo "existing immutable release differs: $RELEASE" >&2; exit 1; }
  done
else
  mv "$STAGING" "$RELEASE"
  trap - 0
fi
chown -R root:root "$RELEASE"
chmod 0755 "$RELEASE"
chmod 0644 "$RELEASE"/*.py "$RELEASE/SOURCE_COMMIT" "$RELEASE/ava-visual-worker.service"

ln -s "$RELEASE" "$ROOT/.current-$STAMP"
mv -Tf "$ROOT/.current-$STAMP" "$ROOT/current"
install -o root -g root -m 0644 "$RELEASE/ava-visual-worker.service" "$UNIT"
mkdir -p "$DROPIN_DIR"
printf '[Service]\nEnvironmentFile=%s\n' "$QUEUE_ENV" > "$DROPIN.tmp"
install -o root -g root -m 0644 "$DROPIN.tmp" "$DROPIN"
rm -f "$DROPIN.tmp"
systemctl daemon-reload
systemd-analyze verify "$UNIT"
systemctl enable --now ava-visual-worker.service
sleep 1
systemctl is-enabled --quiet ava-visual-worker.service
systemctl is-active --quiet ava-visual-worker.service

{
  printf 'activated_at_utc=%s\n' "$STAMP"
  printf 'source_commit=%s\n' "$COMMIT"
  printf 'release=%s\n' "$RELEASE"
  printf 'queue_environment_file=%s\n' "$QUEUE_ENV"
  printf 'previous_current=%s\n' "$PREV_CURRENT"
  printf 'previous_unit=%s\nprevious_dropin=%s\nprevious_active=%s\nprevious_enabled=%s\n' "$PREV_UNIT" "$PREV_DROPIN" "$PREV_ACTIVE" "$PREV_ENABLED"
  systemctl show ava-visual-worker.service -p LoadState -p ActiveState -p SubState -p UnitFileState -p MainPID -p ExecMainStatus
} > "$EVIDENCE/result.txt"
sha256sum "$RELEASE"/*.py "$UNIT" "$DROPIN" > "$EVIDENCE/sha256-manifest.txt"

cat > "$EVIDENCE/rollback.sh" <<ROLLBACK
#!/bin/sh
set -eu
ROOT='$ROOT'
UNIT='$UNIT'
DROPIN_DIR='$DROPIN_DIR'
DROPIN='$DROPIN'
BACKUP='$BACKUP'
PREV_CURRENT='$PREV_CURRENT'
PREV_UNIT='$PREV_UNIT'
PREV_DROPIN='$PREV_DROPIN'
PREV_ACTIVE='$PREV_ACTIVE'
PREV_ENABLED='$PREV_ENABLED'
if [ "\$PREV_CURRENT" != '' ]; then ln -sfn "\$PREV_CURRENT" "\$ROOT/current"; else rm -f "\$ROOT/current"; fi
if [ "\$PREV_UNIT" = 1 ]; then install -o root -g root -m 0644 "\$BACKUP/ava-visual-worker.service" "\$UNIT"; else systemctl disable --now ava-visual-worker.service || true; rm -f "\$UNIT"; fi
if [ "\$PREV_DROPIN" = 1 ]; then mkdir -p "\$DROPIN_DIR"; install -o root -g root -m 0644 "\$BACKUP/queue-env.conf" "\$DROPIN"; else rm -f "\$DROPIN"; fi
systemctl daemon-reload
if [ "\$PREV_UNIT" = 1 ]; then
  if [ "\$PREV_ENABLED" = 1 ]; then systemctl enable ava-visual-worker.service; else systemctl disable ava-visual-worker.service || true; fi
  if [ "\$PREV_ACTIVE" = 1 ]; then systemctl restart ava-visual-worker.service; else systemctl stop ava-visual-worker.service || true; fi
fi
ROLLBACK
chmod 0700 "$EVIDENCE/rollback.sh"
printf 'AVA_VISUAL_ACTIVATION=PASS\ncommit=%s\nevidence=%s\nrollback=%s\n' "$COMMIT" "$EVIDENCE" "$EVIDENCE/rollback.sh"
