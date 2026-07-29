#!/usr/bin/env bash
set -euo pipefail

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)"
cd "$ROOT"

python3 -m py_compile \
  server/network_defense_exporter.py \
  server/network_defense_dns_exporter.py

python3 tests/validate_network_defense_observability.py
python3 tests/validate_network_defense_dns.py
python3 tests/validate_dns_defense_policy.py
python3 tests/validate_network_defense_deployment.py

python3 - <<'PY'
from html.parser import HTMLParser
from pathlib import Path
import subprocess
import tempfile

for page in (
    Path('src/web/network-defense/index.html'),
    Path('src/web/operations-center/index.html'),
    Path('src/web/security/correlation.html'),
):
    class Scripts(HTMLParser):
        def __init__(self):
            super().__init__()
            self.active = False
            self.parts = []
            self.scripts = []
        def handle_starttag(self, tag, attrs):
            if tag == 'script':
                self.active = True
                self.parts = []
        def handle_data(self, data):
            if self.active:
                self.parts.append(data)
        def handle_endtag(self, tag):
            if tag == 'script' and self.active:
                self.scripts.append(''.join(self.parts))
                self.active = False

    parser = Scripts()
    parser.feed(page.read_text(encoding='utf-8'))
    with tempfile.NamedTemporaryFile('w', suffix='.js') as handle:
        handle.write('\n'.join(parser.scripts))
        handle.flush()
        subprocess.run(['node', '--check', handle.name], check=True)

PY

sh -n deploy/install-network-defense-observability.sh
sh -n tools/networking/build-dns-defense-staging.sh
sh -n tools/networking/validate-dns-defense-policy.sh
sh -n tools/networking/validate-dns-network-defense-integration.sh

printf '%s\n' 'Network Defense deployment validation passed.'
