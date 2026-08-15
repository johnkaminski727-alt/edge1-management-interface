#!/bin/sh
set -eu

HOSTNAME_TO_CHECK=${WWCX_NTS_HOSTNAME:-ntp.ww.cx}
FOUND=0

[ "$(id -u)" -eq 0 ] || {
  echo "Run with sudo/root to inspect certificate path metadata without reading private-key contents." >&2
  exit 1
}

command -v openssl >/dev/null 2>&1 || { echo "openssl is required" >&2; exit 1; }
command -v find >/dev/null 2>&1 || { echo "find is required" >&2; exit 1; }

printf 'Searching existing public certificates for hostname %s\n' "$HOSTNAME_TO_CHECK"

for root in /etc/letsencrypt/live /var/lib/acme /var/lib/caddy; do
  [ -d "$root" ] || continue
  find "$root" -maxdepth 5 \( -type f -o -type l \) \
    \( -name 'fullchain.pem' -o -name 'cert.pem' -o -name '*.crt' -o -name '*.cer' \) -print 2>/dev/null |
  while IFS= read -r cert; do
    [ -n "$cert" ] || continue
    if openssl x509 -in "$cert" -noout -checkhost "$HOSTNAME_TO_CHECK" >/dev/null 2>&1; then
      FOUND=1
      echo "MATCH certificate=$cert"
      openssl x509 -in "$cert" -noout -subject -issuer -dates -ext subjectAltName 2>/dev/null || true
      cert_dir=$(dirname "$cert")
      key="$cert_dir/privkey.pem"
      if [ -e "$key" ]; then
        stat -Lc 'matching_key_path=%n owner=%U:%G mode=%a bytes=%s contents_read=no' "$key" 2>/dev/null || \
          echo "matching_key_path=$key contents_read=no"
      else
        echo "matching_key_path=not_found_next_to_certificate"
      fi
      echo "---"
    fi
  done
done

# The loop above may execute in a pipeline subshell on POSIX shells. Perform a
# separate count without relying on shell state to produce an unambiguous exit.
MATCH_COUNT=0
for cert in $(find /etc/letsencrypt/live /var/lib/acme /var/lib/caddy -maxdepth 5 \( -type f -o -type l \) \
  \( -name 'fullchain.pem' -o -name 'cert.pem' -o -name '*.crt' -o -name '*.cer' \) -print 2>/dev/null || true); do
  if openssl x509 -in "$cert" -noout -checkhost "$HOSTNAME_TO_CHECK" >/dev/null 2>&1; then
    MATCH_COUNT=$((MATCH_COUNT + 1))
  fi
done

if [ "$MATCH_COUNT" -eq 0 ]; then
  echo "No existing certificate matching $HOSTNAME_TO_CHECK was found in the reviewed certificate roots."
  exit 2
fi

echo "Found $MATCH_COUNT existing certificate candidate(s) matching $HOSTNAME_TO_CHECK."
