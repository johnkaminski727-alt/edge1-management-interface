#!/usr/bin/env bash
set -euo pipefail

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)"
cd "$ROOT"

PYTHON_BIN="${PYTHON_BIN:-python3}"
NODE_BIN="${NODE_BIN:-node}"

printf '%s\n' '== Python syntax =='
"$PYTHON_BIN" -m py_compile server/security_correlation_exporter.py

printf '%s\n' '== Targeted tests =='
"$PYTHON_BIN" -m unittest \
  tests.test_security_console \
  tests.test_security_correlation \
  -v

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
! grep -Eiq 'fetch\([^)]*,[[:space:]]*\{[^}]*method[[:space:]]*:[[:space:]]*["'"'](POST|PUT|PATCH|DELETE)' \
  src/web/security/index.html \
  src/web/security/correlation.html

grep -Fq 'read_only' server/security_correlation_exporter.py
grep -Fq 'NoNewPrivileges=true' deploy/systemd/wwcx-security-correlation.service
grep -Fq 'ProtectSystem=strict' deploy/systemd/wwcx-security-correlation.service
grep -Fq 'OnUnitActiveSec=1min' deploy/systemd/wwcx-security-correlation.timer

if command -v systemd-analyze >/dev/null 2>&1; then
  printf '%s\n' '== systemd unit verification =='
  systemd-analyze verify \
    deploy/systemd/wwcx-security-correlation.service \
    deploy/systemd/wwcx-security-correlation.timer
fi

printf '%s\n' 'Security correlation validation passed.'
