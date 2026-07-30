#!/usr/bin/env bash
set -Eeuo pipefail

REPO_ROOT=${EDGE1_MANAGEMENT_ROOT:-/opt/edge1-management-interface}
EVIDENCE_ROOT=${EDGE1_DEPLOYMENT_EVIDENCE_ROOT:-/var/lib/wwcx-deployment-evidence/edge1-security-completion-preflight}
STATUS_ROOT=${EDGE1_STATUS_ROOT:-/var/www/edge1-status}
AUTH_USER_FILE=${EDGE1_AUTH_USER_FILE:-}
ACCEPTANCE_FILE=${EDGE1_AUTH_ACCEPTANCE_FILE:-}
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
EVIDENCE_DIR="$EVIDENCE_ROOT/$STAMP"

fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
[ "$(id -u)" -eq 0 ] || fail "run as root"
[ -d "$REPO_ROOT/.git" ] || fail "repository not found: $REPO_ROOT"
for command in bash git python3 curl find stat sha256sum df hostname id systemctl ss tar openssl; do
  command -v "$command" >/dev/null 2>&1 || fail "required command unavailable: $command"
done
install -d -o root -g root -m 0700 "$EVIDENCE_DIR"
hostname -f >"$EVIDENCE_DIR/hostname.txt" 2>&1 || hostname >"$EVIDENCE_DIR/hostname.txt"
id >"$EVIDENCE_DIR/principal.txt"
uname -a >"$EVIDENCE_DIR/uname.txt"
df -Pk "$REPO_ROOT" "$STATUS_ROOT" /var/lib >"$EVIDENCE_DIR/filesystem-capacity.txt" 2>&1 || true

git -C "$REPO_ROOT" status --short --branch >"$EVIDENCE_DIR/repository-status.txt"
git -C "$REPO_ROOT" rev-parse HEAD >"$EVIDENCE_DIR/repository-revision.txt"
[ "$(git -C "$REPO_ROOT" branch --show-current)" = main ] || fail "preflight requires main"
[ -z "$(git -C "$REPO_ROOT" status --porcelain)" ] || fail "preserve unrelated dirty work before deployment"
python3 "$REPO_ROOT/tests/validate_edge1_security_completion.py" | tee "$EVIDENCE_DIR/repository-validation.txt"

APACHE_CTL=""
for candidate in apache2ctl apachectl httpd; do
  if command -v "$candidate" >/dev/null 2>&1; then APACHE_CTL=$candidate; break; fi
done
[ -n "$APACHE_CTL" ] || fail "Apache control command is unavailable"
"$APACHE_CTL" -t >"$EVIDENCE_DIR/apache-config-test.txt" 2>&1
"$APACHE_CTL" -S >"$EVIDENCE_DIR/apache-vhosts.txt" 2>&1
"$APACHE_CTL" -M >"$EVIDENCE_DIR/apache-modules.txt" 2>&1
for module in auth_form_module session_module session_cookie_module session_crypto_module authn_file_module authz_user_module alias_module headers_module ratelimit_module setenvif_module; do
  grep -q " $module " "$EVIDENCE_DIR/apache-modules.txt" || fail "required Apache module is not enabled: $module"
done

if [ -n "$AUTH_USER_FILE" ]; then
  [ -f "$AUTH_USER_FILE" ] || fail "EDGE1_AUTH_USER_FILE is not a file"
  [ "$(stat -c %u "$AUTH_USER_FILE")" -eq 0 ] || fail "authentication file must be root-owned"
  [ "$(stat -c %a "$AUTH_USER_FILE")" -le 640 ] || fail "authentication file mode must be 0640 or stricter"
  printf '%s\n' "$AUTH_USER_FILE" >"$EVIDENCE_DIR/auth-user-file-path.txt"
else
  printf 'not supplied; stage/cutover remains blocked\n' >"$EVIDENCE_DIR/auth-user-file-path.txt"
fi
if [ -n "$ACCEPTANCE_FILE" ]; then
  [ -f "$ACCEPTANCE_FILE" ] || fail "EDGE1_AUTH_ACCEPTANCE_FILE is not a file"
  [ "$(stat -c %u "$ACCEPTANCE_FILE")" -eq 0 ] || fail "acceptance credential file must be root-owned"
  [ "$(stat -c %a "$ACCEPTANCE_FILE")" -le 600 ] || fail "acceptance credential file mode must be 0600 or stricter"
  printf 'present and protected\n' >"$EVIDENCE_DIR/acceptance-credential-state.txt"
else
  printf 'not supplied; authenticated acceptance and cutover remain blocked\n' >"$EVIDENCE_DIR/acceptance-credential-state.txt"
fi

systemctl show suricata.service -p LoadState -p ActiveState -p SubState -p FragmentPath >"$EVIDENCE_DIR/suricata-service-before.txt" 2>&1 || true
systemctl show wwcx-network-defense.timer -p ActiveState -p UnitFileState >"$EVIDENCE_DIR/network-defense-timer-before.txt" 2>&1 || true
ss -H -lntup 2>/dev/null | sort >"$EVIDENCE_DIR/listeners-before.txt" || true
if command -v nft >/dev/null 2>&1; then nft -j list ruleset 2>/dev/null | sha256sum >"$EVIDENCE_DIR/nftables-before.sha256" || true; fi
if [ -d /etc/suricata ]; then find /etc/suricata -xdev -type f -print0 | sort -z | xargs -0 -r sha256sum >"$EVIDENCE_DIR/suricata-config-before.sha256"; fi
find "$STATUS_ROOT" -xdev -maxdepth 6 -type f -printf '%m\t%u\t%g\t%s\t%p\n' | sort >"$EVIDENCE_DIR/detailed-public-inventory.txt" 2>&1 || true
find "$STATUS_ROOT" -xdev -maxdepth 6 -type f -print0 | sort -z | xargs -0 -r sha256sum >"$EVIDENCE_DIR/detailed-public.sha256" 2>&1 || true
find "$EVIDENCE_DIR" -maxdepth 1 -type f ! -name manifest.sha256 -print0 | sort -z | xargs -0 sha256sum >"$EVIDENCE_DIR/manifest.sha256"
printf '%s\n' "$EVIDENCE_DIR"
