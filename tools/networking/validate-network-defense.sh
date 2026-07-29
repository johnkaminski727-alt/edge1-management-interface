#!/usr/bin/env bash
set -euo pipefail
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)"
cd "$ROOT"
python3 -m py_compile server/network_defense_exporter.py
python3 -m unittest tests.test_network_defense_exporter tests.test_network_defense_console -v
node --check <(python3 - <<'PY'
from html.parser import HTMLParser
from pathlib import Path
class P(HTMLParser):
 def __init__(self): super().__init__(); self.x=[]; self.a=False
 def handle_starttag(self,t,a): self.a=t=='script'
 def handle_data(self,d):
  if self.a:self.x.append(d)
p=P();p.feed(Path('src/web/network-defense/index.html').read_text())
print('\n'.join(p.x))
PY
)
sh -n tools/networking/validate-network-defense.sh
printf '%s\n' 'Network defense validation passed.'
