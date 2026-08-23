#!/usr/bin/env bash
set -euo pipefail

REPO=/opt/edge1-management-interface
REF=origin/main
DRY_RUN=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo) REPO="$2"; shift 2 ;;
    --ref) REF="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

ROOT=/opt/wwcx/ava-visual
UNIT=/etc/systemd/system/ava-visual-worker.service
EVIDENCE_ROOT=/var/lib/wwcx-deployment-evidence/ava-visual
BACKUP_ROOT=/var/backups/wwcx-ava-visual
STAMP=$(date -u +%Y%m%dT%H%M%SZ)

[[ -d "$REPO/.git" || -f "$REPO/.git" ]] || { echo "repository unavailable: $REPO" >&2; exit 1; }
git -C "$REPO" cat-file -e "$REF^{commit}"
COMMIT=$(git -C "$REPO" rev-parse "$REF^{commit}")
for path in server/ava_visual_worker.py server/ava_visual_generator.py server/private_ai_browser_worker.py deploy/ava-visual-worker.service; do
  git -C "$REPO" cat-file -e "$REF:$path"
done

if [[ "$DRY_RUN" == 1 ]]; then
  printf 'mode=dry-run\nrepo=%s\nref=%s\ncommit=%s\nruntime_root=%s\nunit=%s\n' "$REPO" "$REF" "$COMMIT" "$ROOT" "$UNIT"
  exit 0
fi

[[ $(id -u) -eq 0 ]] || { echo "activation must run as root" >&2; exit 1; }
[[ $(hostname -f 2>/dev/null || hostname) == edge1.ww.cx ]] || { echo "refusing activation on non-Edge1 host" >&2; exit 1; }
getent passwd bigbird-ai >/dev/null
getent group bigbird-ai >/dev/null
[[ -r /etc/bigbird-ai-gateway.env ]] || { echo "Private AI gateway environment is unavailable" >&2; exit 1; }
[[ -r /etc/wwcx/private-ai-browser-worker.env ]] || { echo "browser worker environment is unavailable" >&2; exit 1; }
grep -q '^OPENAI_API_KEY=' /etc/bigbird-ai-gateway.env || { echo "OPENAI_API_KEY is not configured in the gateway environment" >&2; exit 1; }
grep -q '^BB_BROWSER_WORKER_SECRET=' /etc/wwcx/private-ai-browser-worker.env || { echo "queue signing secret is not configured" >&2; exit 1; }
grep -q '^BB_BROWSER_WORKER_KEY_ID=' /etc/wwcx/private-ai-browser-worker.env || { echo "queue key id is not configured" >&2; exit 1; }

EVIDENCE="$EVIDENCE_ROOT/$STAMP"
BACKUP="$BACKUP_ROOT/$STAMP"
STAGING="$ROOT/releases/.staging-$STAMP"
RELEASE="$ROOT/releases/$COMMIT"
mkdir -p "$EVIDENCE" "$BACKUP" "$ROOT/releases"
chmod 0750 "$EVIDENCE" "$BACKUP" "$ROOT" "$ROOT/releases"
mkdir "$STAGING"
trap 'rm -rf "$STAGING"' EXIT

for name in ava_visual_worker.py ava_visual_generator.py private_ai_browser_worker.py; do
  git -C "$REPO" show "$REF:server/$name" > "$STAGING/$name"
done
git -C "$REPO" show "$REF:deploy/ava-visual-worker.service" > "$STAGING/ava-visual-worker.service"
printf '%s\n' "$COMMIT" > "$STAGING/SOURCE_COMMIT"
chmod 0644 "$STAGING"/*.py "$STAGING/ava-visual-worker.service "$STAGING/SOURCE_COMMIT"
python3 -m py_compile "$STAGING/ava_visual_worker.py" "$STAGING/ava_visual_generator.py" "$STAGING/private_ai_browser_worker.py"
systemd-analyze verify "$STAGING/ava-visual-worker.service"

PREV_CURRENT=''
if [[ -L "$ROOT/current" ]]; then PREV_CURRENT=$(readlink -f "$ROOT/current" || true); fi
PREV_UNIT=0; PREV_ACTIVE=0; PREV_ENABLED=0
if [[ -f "$UNIT" ]]; then cp -a "$UNIT" "$BACKUP/ava-visual-worker.service"; PREV_UNIT=1; fi
if systemctl is-active --quiet ava-visual-worker.service 2>/dev/null; then PREV_ACTIVE=1; fi
if systemctl is-enabled --quiet ava-visual-worker.service 2>/dev/null; then PREV_ENABLED=1; fi

if [[ -e "$RELEASE" ]]; then
  for name in ava_visual_worker.py ava_visual_generator.py private_ai_browser_worker.py SOURCE_COMMIT; do
    cmp -s "$STAGING/$name" "$RELEASE/$name" || { echo "existing immutable release differs: $RELEASE" >&2; exit 1; }
  done
else
  mv "$STAGING" "$RELEASE"
  trap - EXIT
fi
chown -R root:root "$RELEASE"
chmod 0755 "$RELEASE"
chmod 0644 "$RELEASE"/*.py "$RELEASE/SOURCE_COMMIT"

ln -s "$RELEASE" "$ROOT/.current-$STAMP"
mv -Tf "$ROOT/.current-$STAMP" "$ROOT/current"
install -o root -g root -m 0644 "$RELEASE/ava-visual-worker.service" "$UNIT"
systemctl daemon-reload
systemctl enable --now ava-visual-worker.service
sleep 1
systemctl is-enabled --quiet ava-visual-worker.service
systemctl is-active --quiet ava-visual-worker.service

{
  printf 'activated_at_utc=%s\n' "$STAMP"
  printf 'source_commit=%s\n' "$COMMIT"
  printf 'release=%s\n' "$RELEASE"
  printf 'previous_current=%s\n' "$PREV_CURRENT"
  printf 'previous_unit=%s\nprevious_active=%s\nprevious_enabled=%s\n' "$PREV_UNIT" "$PREV_ACTIVE" "$PREV_ENABLED"
  systemctl show ava-visual-worker.service -p LoadState -p ActiveState -p SubState -p UnitFileState -p MainPID -p ExecMainStatus
} > "$EVIDENCE/result.txt"
sha256sum "$RELEASE/ava_visual_worker.py" "$RELEASE/ava_visual_generator.py" "$RELEASE/private_ai_browser_worker.py" "$UNIT" > "$EVIDENCE/sha256-manifest.txt"

cat > "$EVIDENCE/rollback.sh" <<ROLLBACK
#!/usr/bin/env bash
set -euo pipefail
ROOT='$ROOT'
UNIT='$UNIT'
BACKUP='$BACKUP'
PREV_CURRENT='$PREV_CURRENT'
PREV_UNIT='$PREV_UNIT'
PREV_ACTIVE='$PREV_ACTIVE'
PREV_ENABLED='$PREV_ENABLED'
if [[ \"\$PREV_CURRENT\" != '' ]]; then ln -sfn \"\$PREV_CURRENT\" \"\$ROOT/current\"; else rm -f \"\$ROOT/current\"; fi
if [[ \"\$PREV_UNIT\" == 1 ]]; then install -o root -g root -m 0644 \"\$BACKUP/ava-visual-worker.service\" \"\$UNIT\"; else systemctl disable --now ava-visual-worker.service || true; rm -f \"\$UNIT\"; fi
systemctl daemon-reload
if [[ \"\$PREV_UNIT\" == 1 ]]; then
  if [[ \"\$PREV_ENABLED\" == 1 ]]; then systemctl enable ava-visual-worker.service; else systemctl disable ava-visual-worker.service || true; fi
  if [[ \"\$PREV_ACTIVE\" == 1 ]]; then systemctl restart ava-visual-worker.service; else systemctl stop ava-visual-worker.service || true; fi
fi
ROLLBACK
chmod 0700 "$EVIDENCE/rollback.sh"
printf 'AVA_VISUAL_ACTIVATION=PASS\ncommit=%s\nevidence=%s\nrollback=%s\n' "$COMMIT" "$EVIDENCE" "$EVIDENCE/rollback.sh"
