#!/usr/bin/env python3
"""Validate official Spamhaus line-delimited DROP JSON and render an nft candidate.

No network operations, nft commands, or firewall mutations occur in this module.
"""
from __future__ import annotations

import argparse
import datetime as dt
import ipaddress
import json
from pathlib import Path

MAX_FEED_BYTES = 8 * 1024 * 1024
MAX_RECORDS = 100_000
MAX_FEED_AGE = dt.timedelta(hours=72)
CLOCK_SKEW = dt.timedelta(minutes=15)


def parse_feed(path: Path, family: int, now: dt.datetime | None = None) -> tuple[list, int]:
    current = now or dt.datetime.now(dt.timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now must have timezone")
    if path.stat().st_size > MAX_FEED_BYTES:
        raise ValueError("Feed exceeds 8 MiB safety limit")
    networks = set()
    timestamps = []
    record_count = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record_count += 1
        if record_count > MAX_RECORDS:
            raise ValueError("Too many feed records")
        record = json.loads(line)
        if not isinstance(record, dict):
            raise ValueError("Feed record is not a JSON object")
        if "cidr" in record:
            if not isinstance(record["cidr"], str):
                raise ValueError("CIDR field must be a string")
            network = ipaddress.ip_network(record["cidr"], strict=True)
            if network.version != family or not network.is_global:
                raise ValueError("Invalid address family or non-global prefix")
            networks.add(network)
        elif "timestamp" in record:
            value = record["timestamp"]
            if type(value) is not int:
                raise ValueError("Publication timestamp must be Unix integer")
            timestamps.append(value)
        else:
            raise ValueError("Unrecognized feed record")
    if not networks or len(timestamps) != 1:
        raise ValueError("Expected nonempty feed and exactly one metadata timestamp")
    published = dt.datetime.fromtimestamp(timestamps[0], dt.timezone.utc)
    age = current - published
    if age < -CLOCK_SKEW or age > MAX_FEED_AGE:
        raise ValueError("Feed publication age outside permitted window")
    collapsed = list(ipaddress.collapse_addresses(networks))
    return collapsed, len(networks)


def render_candidate(v4: list, v6: list, *, replace: bool = False) -> str:
    if not v4 or not v6:
        raise ValueError("IPv4 and IPv6 feeds are both required")
    def entries(items):
        return ",\n      ".join(map(str, items))
    prefix = "delete table inet bigbird_spamhaus\n\n" if replace else ""
    return f"""{prefix}table inet bigbird_spamhaus {{
  set drop4 {{
    type ipv4_addr
    flags interval
    elements = {{
      {entries(v4)}
    }}
  }}
  set drop6 {{
    type ipv6_addr
    flags interval
    elements = {{
      {entries(v6)}
    }}
  }}
  chain input {{
    type filter hook input priority -110; policy accept;
    ip saddr @drop4 counter drop
    ip6 saddr @drop6 counter drop
  }}
  chain forward {{
    type filter hook forward priority -110; policy accept;
    ip saddr @drop4 counter drop
    ip6 saddr @drop6 counter drop
  }}
}}
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ipv4", type=Path, required=True)
    parser.add_argument("--ipv6", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    v4, v4_unique = parse_feed(args.ipv4, 4)
    v6, v6_unique = parse_feed(args.ipv6, 6)
    args.output.write_text(render_candidate(v4, v6, replace=args.replace), encoding="utf-8")
    args.summary.write_text(
        f"drop4={v4_unique}\ncombined4={len(v4)}\ndrop6={len(v6)}\n"
        "feed_format=spamhaus_drop_json\n",
        encoding="utf-8",
    )
    print(f"Validated IPv4={v4_unique}, IPv6={v6_unique}; candidate generated. No rules applied.")


if __name__ == "__main__":
    main()
