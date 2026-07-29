#!/usr/bin/env bash
set -euo pipefail

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)"
cd "$ROOT"

PYTHON_BIN="${PYTHON_BIN:-python3}"
NODE_BIN="${NODE_BIN:-node}"

printf '%s\n' '== Python syntax =='
"$PYTHON_BIN" -m py_compile \
  server/security_correlation_exporter.py \
  tools/security/verify_security_observability.py

printf '%s\n' '== Targeted tests =='
"$PYTHON_BIN" -m unittest \
  tests.test_security_console \
  tests.test_security_correlation \
  tests.test_security_correlation_deployment \
  tests.test_security_observability_acceptance \
  -v

printf '%s\n' '== Shell syntax =='
bash -n deploy/install-security-correlation-observability.sh
bash -n tools/security/verify-security-observability-live.sh

printf '%s\n' '== Inline JavaScript syntax =='
"$PYTHON_BIN" - "$NODE_BIN" <<'PY'
from html.parser import HTMLParser
from pathlib import Path
import subprocess
import sys
import tempfile

node = sys.argv[1]
files = (
    Path('src/web/security/index.html'),
    Path('src/web/security/correlation.html'),
)

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

for path in files:
    parser = Scripts()
    parser.feed(path.read_text(encoding='utf-8'))
    source = '\n'.join(parser.scripts)
    with tempfile.NamedTemporaryFile('w', suffix='.js', encoding='utf-8') as handle:
        handle.write(source)
        handle.flush()
        subprocess.run([node, '--check', handle.name], check=True)
    print(f'JavaScript valid: {path}')
PY

printf '%s\n' '== Read-only boundary =='
"$PYTHON_BIN" - <<'PY'
from pathlib import Path
import re

pattern = re.compile(
    r'''fetch\s*\([^)]*,\s*\{[^}]*method\s*:\s*["'](?:POST|PUT|PATCH|DELETE)["']''',
    re.IGNORECASE | re.DOTALL,
)
for path in (
    Path('src/web/security/index.html'),
    Path('src/web/security/correlation.html'),
):
    if pattern.search(path.read_text(encoding='utf-8')):
        raise SystemExit(f'write-capable fetch detected: {path}')
PY

grep -Fq 'read_only' server/security_correlation_exporter.py
grep -Fq 'NoNewPrivileges=true' deploy/systemd/wwcx-security-correlation.service
grep -Fq 'ProtectSystem=strict' deploy/systemd/wwcx-security-correlation.service
grep -Fq 'ReadWritePaths=/var/www/edge1-status/security/correlation/data' deploy/systemd/wwcx-security-correlation.service
grep -Fq 'CapabilityBoundingSet=' deploy/systemd/wwcx-security-correlation.service
grep -Fq 'OnUnitActiveSec=1min' deploy/systemd/wwcx-security-correlation.timer
grep -Fq 'traffic_controls_changed' tools/security/verify_security_observability.py

if command -v systemd-analyze >/dev/null 2>&1; then
  printf '%s\n' '== systemd unit verification =='
  systemd-analyze verify \
    deploy/systemd/wwcx-security-correlation.service \
    deploy/systemd/wwcx-security-correlation.timer
fi

printf '%s\n' 'Security correlation validation passed.'
