#!/usr/bin/env bash
set -euo pipefail
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)"
cd "$ROOT"
python3 -m py_compile tools/networking/compile-dns-defense-policy.py tests/test_dns_defense_policy.py tests/validate_dns_defense_policy.py
python3 tests/validate_dns_defense_policy.py
work_dir="$(mktemp -d)"
trap 'rm -rf "$work_dir"' EXIT
python3 tools/networking/compile-dns-defense-policy.py \
  --policy config/dns-defense/policy.example.json \
  --output-dir "$work_dir"
grep -Fq 'rpz-action-override: disabled' "$work_dir/wwcx-dns-defense-staged.conf"
grep -Fq 'malware.invalid CNAME .' "$work_dir/wwcx-dns-defense.rpz.zone"
grep -Fq '"enforcement_enabled": false' "$work_dir/dns-defense-policy-status.json"
grep -Fq '"traffic_controls_changed": false' "$work_dir/dns-defense-policy-status.json"
sh -n tools/networking/validate-dns-defense-policy.sh
printf '%s\n' 'DNS Defense policy validation passed.'
