#!/usr/bin/env bash
set -euo pipefail

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)"
cd "$ROOT"

python3 -m py_compile \
  server/network_defense_dns_exporter.py \
  tools/networking/compile-dns-defense-policy.py

python3 tests/validate_dns_defense_policy.py
python3 tests/validate_network_defense_dns.py

sh -n tools/networking/build-dns-defense-staging.sh
sh -n tools/networking/validate-dns-defense-policy.sh

printf '%s\n' 'DNS Defense integration validation passed.'
