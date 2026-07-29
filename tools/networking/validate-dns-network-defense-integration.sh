#!/usr/bin/env bash
set -euo pipefail

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)"
cd "$ROOT"

python3 -m py_compile server/network_defense_dns_exporter.py
python3 tests/validate_network_defense_dns.py

printf '%s\n' 'DNS Network Defense integration validation passed.'
