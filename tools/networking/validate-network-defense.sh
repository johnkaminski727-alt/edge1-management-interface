#!/usr/bin/env bash
set -euo pipefail
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)"
cd "$ROOT"
python3 -m py_compile server/network_defense_exporter.py
python3 -m unittest tests.test_network_defense_exporter tests.test_network_defense_console -v
python3 - <<'PY'
from html.parser import HTMLParser
from pathlib import Path
import subprocess
import tempfile

class Parser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active=False
        self.parts=[]
        self.scripts=[]
    def handle_starttag(self, tag, attrs):
        if tag == 'script':
            self.active=True
            self.parts=[]
    def handle_data(self, data):
        if self.active:
            self.parts.append(data)
    def handle_endtag(self, tag):
        if tag == 'script' and self.active:
            self.scripts.append(''.join(self.parts))
            self.active=False

parser=Parser()
parser.feed(Path('src/web/network-defense/index.html').read_text(encoding='utf-8'))
with tempfile.NamedTemporaryFile('w', suffix='.js', encoding='utf-8') as handle:
    handle.write('\n'.join(parser.scripts))
    handle.flush()
    subprocess.run(['node','--check',handle.name], check=True)
PY
sh -n tools/networking/validate-network-defense.sh
printf '%s\n' 'Network defense validation passed.'
