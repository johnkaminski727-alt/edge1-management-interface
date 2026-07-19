#!/bin/sh
set -eu

OUT=${1:-"$HOME/wwcx-interconnect-preflight-$(date +%Y%m%d-%H%M%S).txt"}

{
  echo "WW.CX SIP INTERCONNECT READ-ONLY PREFLIGHT"
  echo "Generated: $(date --iso-8601=seconds 2>/dev/null || date)"
  echo

  echo "== Identity =="
  hostnamectl 2>/dev/null || true
  id
  echo

  echo "== Operating system =="
  cat /etc/os-release 2>/dev/null || true
  uname -a
  echo

  echo "== Addresses and routes =="
  ip -brief address 2>/dev/null || true
  ip -4 route 2>/dev/null || true
  ip -6 route 2>/dev/null || true
  echo

  echo "== Public address observations =="
  printf 'IPv4: '
  curl -4 -fsS --max-time 10 https://icanhazip.com 2>/dev/null || echo unavailable
  printf 'IPv6: '
  curl -6 -fsS --max-time 10 https://icanhazip.com 2>/dev/null || echo unavailable
  echo

  echo "== Relevant listeners =="
  ss -lntup 2>/dev/null | grep -E ':(443|5060|5061|5070|8093)([[:space:]]|$)' || true
  echo

  echo "== Installed package candidates =="
  dpkg-query -W -f='${binary:Package}\t${Version}\n' \
    kamailio kamailio-tls-modules kamailio-extra-modules asterisk apache2 certbot nftables ufw 2>/dev/null || true
  echo

  echo "== Service state =="
  for unit in asterisk apache2 kamailio nftables ufw; do
    printf '%s: ' "$unit"
    systemctl is-active "$unit" 2>/dev/null || true
  done
  echo

  echo "== DNS =="
  for q in \
    'A interconnect.ww.cx' \
    'AAAA interconnect.ww.cx' \
    'SRV _sips._tcp.ww.cx' \
    'SRV _sips._tcp.interconnect.ww.cx' \
    'NAPTR ww.cx' \
    'NAPTR interconnect.ww.cx'; do
    set -- $q
    echo "-- $1 $2"
    dig +short "$1" "$2" 2>/dev/null || true
  done
  echo

  echo "== Certificate inventory, metadata only =="
  if command -v certbot >/dev/null 2>&1; then
    certbot certificates 2>/dev/null || true
  else
    echo "certbot not installed"
  fi
  echo

  echo "== Asterisk read-only inventory =="
  if command -v asterisk >/dev/null 2>&1; then
    sudo -n asterisk -rx 'core show version' 2>/dev/null || echo 'sudo or Asterisk CLI unavailable'
    sudo -n asterisk -rx 'pjsip show transports' 2>/dev/null || true
    sudo -n asterisk -rx 'pjsip show registrations' 2>/dev/null || true
    sudo -n asterisk -rx 'pjsip show endpoints' 2>/dev/null || true
  fi
  echo

  echo "== Firewall summaries, read-only =="
  sudo -n nft list ruleset 2>/dev/null || echo 'nftables rules unavailable without interactive sudo or not configured'
  sudo -n ufw status verbose 2>/dev/null || true
  echo

  echo "== Resource capacity =="
  free -h 2>/dev/null || true
  df -h / /opt /var 2>/dev/null || true
  nproc 2>/dev/null || true
  echo

  echo "PREFLIGHT COMPLETE"
} | tee "$OUT"

printf '\nSaved to: %s\n' "$OUT"
