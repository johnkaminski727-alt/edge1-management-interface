#!/usr/bin/env bash
set -euo pipefail
OUT="${1:-network-sensor-discovery-$(date -u +%Y%m%dT%H%M%SZ)}"
mkdir -p "$OUT"
{
  hostname -f 2>/dev/null || hostname
  id
  uname -a
} > "$OUT/host.txt"
ip -br link > "$OUT/ip-link.txt"
ip -br addr > "$OUT/ip-addresses.txt"
ip route show table all > "$OUT/routes.txt"
ip rule show > "$OUT/rules.txt"
ss -lntup > "$OUT/listeners.txt" 2>&1 || true
systemctl status suricata --no-pager > "$OUT/suricata-status.txt" 2>&1 || true
suricata --build-info > "$OUT/suricata-build-info.txt" 2>&1 || true
for iface in /sys/class/net/*; do
  name="$(basename "$iface")"
  [ "$name" = lo ] && continue
  ethtool -i "$name" > "$OUT/ethtool-$name-driver.txt" 2>&1 || true
  ethtool "$name" > "$OUT/ethtool-$name-link.txt" 2>&1 || true
  ip -s link show dev "$name" > "$OUT/ip-stats-$name.txt" 2>&1 || true
done
{
  command -v suricata || true
  command -v tcpdump || true
  command -v zeek || true
  command -v jq || true
} > "$OUT/binaries.txt"
sha256sum "$OUT"/* > "$OUT/SHA256SUMS"
printf 'Read-only discovery complete: %s\n' "$OUT"
