#!/usr/bin/env bash
set -euo pipefail

# Creates /etc/nginx/edge1-search.htpasswd for the VPN search route.
# Uses openssl's apr1 hashing so apache2-utils is not required.

HTPASSWD_FILE="${EDGE1_SEARCH_HTPASSWD:-/etc/nginx/edge1-search.htpasswd}"

if [ "${EUID}" -ne 0 ]; then
  echo "create-search-route-htpasswd.sh must run as root" >&2
  exit 1
fi

if [ ! -x /usr/bin/openssl ] && ! command -v openssl >/dev/null 2>&1; then
  echo "Missing required command: openssl" >&2
  exit 1
fi

read -rp "Operator username [operator]: " USERNAME
USERNAME="${USERNAME:-operator}"
case "$USERNAME" in
  *[!a-zA-Z0-9_.-]*)
    echo "Username may only contain letters, digits, dot, dash, underscore" >&2
    exit 1
    ;;
esac

read -rsp "Password: " PASSWORD_1
echo
read -rsp "Password (again): " PASSWORD_2
echo

if [ "$PASSWORD_1" != "$PASSWORD_2" ]; then
  echo "Passwords do not match" >&2
  exit 1
fi
if [ "${#PASSWORD_1}" -lt 12 ]; then
  echo "Password must be at least 12 characters" >&2
  exit 1
fi

HASH="$(printf '%s' "$PASSWORD_1" | openssl passwd -apr1 -stdin)"
umask 027
if [ -f "$HTPASSWD_FILE" ]; then
  # Replace this user's entry if present; keep other operators.
  grep -v "^${USERNAME}:" "$HTPASSWD_FILE" > "${HTPASSWD_FILE}.tmp" || true
  mv "${HTPASSWD_FILE}.tmp" "$HTPASSWD_FILE"
fi
printf '%s:%s\n' "$USERNAME" "$HASH" >> "$HTPASSWD_FILE"
chmod 640 "$HTPASSWD_FILE"
if getent group www-data >/dev/null 2>&1; then
  chown root:www-data "$HTPASSWD_FILE"
elif getent group nginx >/dev/null 2>&1; then
  chown root:nginx "$HTPASSWD_FILE"
fi

echo "Wrote credentials for '${USERNAME}' to ${HTPASSWD_FILE}"
