#!/usr/bin/env python3
"""Static checks for the Edge1 VPN-to-public-address UFW helper."""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'deploy/edge1-vpn-public-access/allow-vpn-to-public-address.sh'

text = SCRIPT.read_text(encoding='utf-8')
subprocess.run(['sh', '-n', str(SCRIPT)], check=True)

# Bounded scope: VPN interface and subnet only, ports 443/22 only.
assert 'VPN_IF=${WWCX_VPN_IF:-wg0}' in text
assert 'VPN_NET=${WWCX_VPN_NET:-10.77.0.0/24}' in text
assert 'PORTS="443 22"' in text
assert 'in on $VPN_IF proto tcp from $VPN_NET to $PUBLIC_IP port $1' in text
for forbidden in ('from any', 'to any', 'ufw disable', 'ufw reset', 'ufw default', 'nft flush', '0.0.0.0/0'):
    assert forbidden not in text, forbidden
# Dry run is the default; apply/remove are explicit; evidence is kept.
assert 'MODE=dry-run' in text and '--apply) MODE=apply' in text and '--remove) MODE=remove' in text
assert 'ufw-status.before.txt' in text and 'ufw-status.after.txt' in text
assert "grep -q '^Status: active'" in text
# No hard-coded public address in the public repository.
assert '89.126.' not in text
print('Edge1 VPN public-access helper validation passed.')
