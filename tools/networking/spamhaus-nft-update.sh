#!/usr/bin/env bash
set -euo pipefail

STATE_DIR="${BB_SPAMHAUS_STATE_DIR:-/var/lib/bigbird-networking/spamhaus}"
NFT="${NFT:-/usr/sbin/nft}"
CURL="${CURL:-/usr/bin/curl}"
PYTHON="${PYTHON:-/usr/bin/python3}"

DROP_URL="${BB_SPAMHAUS_DROP_URL:-https://www.spamhaus.org/drop/drop.txt}"
EDROP_URL="${BB_SPAMHAUS_EDROP_URL:-https://www.spamhaus.org/drop/edrop.txt}"
DROPV6_URL="${BB_SPAMHAUS_DROPV6_URL:-https://www.spamhaus.org/drop/dropv6.txt}"

TABLE_FAMILY="${BB_SPAMHAUS_TABLE_FAMILY:-inet}"
TABLE_NAME="${BB_SPAMHAUS_TABLE_NAME:-bigbird_spamhaus}"
CHAIN_PRIORITY="${BB_SPAMHAUS_CHAIN_PRIORITY:--110}"

require_root() {
  if [ "${EUID}" -ne 0 ]; then
    echo "spamhaus-nft-update must run as root" >&2
    exit 1
  fi
}

require_command() {
  if [ ! -x "$1" ]; then
    echo "Required command is missing or not executable: $1" >&2
    exit 1
  fi
}

download_list() {
  local url="$1"
  local target="$2"
  "$CURL" --fail --silent --show-error --location --retry 3 --retry-delay 5 \
    --connect-timeout 15 --max-time 90 \
    --user-agent "BigBirdEdge1SpamhausFilter/1.1" "$url" > "$target"
}

require_root
require_command "$NFT"
require_command "$CURL"
require_command "$PYTHON"

install -d -m 0755 "$STATE_DIR"
work_dir="$(mktemp -d "${STATE_DIR}/update.XXXXXX")"
trap 'rm -rf "$work_dir"' EXIT

download_list "$DROP_URL" "$work_dir/drop.txt"
download_list "$EDROP_URL" "$work_dir/edrop.txt"

if download_list "$DROPV6_URL" "$work_dir/dropv6.txt"; then
  have_v6=1
else
  have_v6=0
  : > "$work_dir/dropv6.txt"
fi

if "$NFT" list table "$TABLE_FAMILY" "$TABLE_NAME" >/dev/null 2>&1; then
  table_exists=1
else
  table_exists=0
fi

"$PYTHON" - "$work_dir" "$TABLE_FAMILY" "$TABLE_NAME" "$CHAIN_PRIORITY" "$have_v6" "$table_exists" <<'PY'
from __future__ import annotations

import ipaddress
import sys
from pathlib import Path

work_dir = Path(sys.argv[1])
family = sys.argv[2]
table = sys.argv[3]
priority = sys.argv[4]
have_v6 = sys.argv[5] == "1"
table_exists = sys.argv[6] == "1"


def parse_networks(path: Path, version: int) -> list[str]:
    networks = set()
    for line_no, raw in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        text = raw.split(";", 1)[0].strip()
        if not text or text.startswith("#"):
            continue
        token = text.split()[0].strip()
        try:
            network = ipaddress.ip_network(token, strict=False)
        except ValueError as exc:
            raise SystemExit(f"{path.name}:{line_no}: invalid network {token!r}: {exc}")
        if network.version != version:
            raise SystemExit(f"{path.name}:{line_no}: expected IPv{version}, got {network}")
        if network.is_private or network.is_loopback or network.is_link_local or network.is_multicast:
            raise SystemExit(f"{path.name}:{line_no}: refusing suspicious network {network}")
        networks.add(network)
    return [str(network) for network in ipaddress.collapse_addresses(sorted(networks))]


drop4 = parse_networks(work_dir / "drop.txt", 4)
edrop4 = parse_networks(work_dir / "edrop.txt", 4)
drop6 = parse_networks(work_dir / "dropv6.txt", 6) if have_v6 else []

if not drop4:
    raise SystemExit("Spamhaus DROP list parsed as empty; refusing to change nftables")

all4 = [
    str(network)
    for network in ipaddress.collapse_addresses(
        sorted({ipaddress.ip_network(item) for item in drop4 + edrop4})
    )
]


def elements(items: list[str]) -> str:
    return ",\n      ".join(items) if items else ""


drop6_set = ""
drop6_rules = ""
if drop6:
    drop6_set = f"""

  set drop6 {{
    type ipv6_addr
    flags interval
    elements = {{
      {elements(drop6)}
    }}
  }}"""
    drop6_rules = """
    ip6 saddr @drop6 counter drop"""

prefix = f"delete table {family} {table}\n\n" if table_exists else ""

ruleset = f"""{prefix}table {family} {table} {{

  set drop4 {{
    type ipv4_addr
    flags interval
    elements = {{
      {elements(all4)}
    }}
  }}{drop6_set}

  chain input {{
    type filter hook input priority {priority}; policy accept;
    ip saddr @drop4 counter drop{drop6_rules}
  }}

  chain forward {{
    type filter hook forward priority {priority}; policy accept;
    ip saddr @drop4 counter drop{drop6_rules}
  }}
}}
"""

(work_dir / "spamhaus.nft").write_text(ruleset, encoding="utf-8")
(work_dir / "summary.txt").write_text(
    f"drop4={len(drop4)}\nedrop4={len(edrop4)}\ncombined4={len(all4)}\ndrop6={len(drop6)}\n",
    encoding="utf-8",
)
PY

"$NFT" -c -f "$work_dir/spamhaus.nft"
"$NFT" -f "$work_dir/spamhaus.nft"

install -m 0644 "$work_dir/drop.txt" "$STATE_DIR/drop.txt"
install -m 0644 "$work_dir/edrop.txt" "$STATE_DIR/edrop.txt"
install -m 0644 "$work_dir/dropv6.txt" "$STATE_DIR/dropv6.txt"
install -m 0644 "$work_dir/spamhaus.nft" "$STATE_DIR/spamhaus.nft"
install -m 0644 "$work_dir/summary.txt" "$STATE_DIR/summary.txt"

echo "Spamhaus nftables filter applied."
cat "$STATE_DIR/summary.txt"
