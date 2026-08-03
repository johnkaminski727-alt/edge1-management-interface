#!/usr/bin/env bash
set -euo pipefail
. /etc/default/wwcx-network-sensor
: "${PCAP_RETENTION_DAYS:=7}"
: "${PCAP_MAX_GB:=250}"
: "${EXTRACTED_RETENTION_DAYS:=14}"
: "${METADATA_RETENTION_DAYS:=90}"
PCAP=/var/lib/wwcx-network-sensor/pcap
EXTRACTED=/var/lib/wwcx-network-sensor/extracted
METADATA=/var/log/wwcx-network-sensor
find "$PCAP" -type f -name '*.pcap*' -mtime "+$PCAP_RETENTION_DAYS" -delete 2>/dev/null || true
find "$EXTRACTED" -type f -mtime "+$EXTRACTED_RETENTION_DAYS" -delete 2>/dev/null || true
find "$METADATA" -type f -mtime "+$METADATA_RETENTION_DAYS" -delete 2>/dev/null || true
max_bytes=$((PCAP_MAX_GB * 1024 * 1024 * 1024))
current_bytes="$(du -sb "$PCAP" 2>/dev/null | awk '{print $1}')"
current_bytes="${current_bytes:-0}"
if [ "$current_bytes" -gt "$max_bytes" ]; then
  oldest_files="$(mktemp)"
  trap 'rm -f "$oldest_files"' EXIT INT TERM
  find "$PCAP" -type f -name '*.pcap*' -printf '%T@ %p\n' |
    sort -n |
    cut -d' ' -f2- > "$oldest_files"
  while IFS= read -r file; do
    [ "$current_bytes" -le "$max_bytes" ] && break
    size="$(stat -c %s "$file" 2>/dev/null || echo 0)"
    rm -f -- "$file"
    current_bytes=$((current_bytes - size))
  done < "$oldest_files"
  rm -f "$oldest_files"
  trap - EXIT INT TERM
fi
