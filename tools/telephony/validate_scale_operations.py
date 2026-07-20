#!/usr/bin/env python3

import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]

FILES = [
    "data/registry/interconnect/regions/regions.json",
    "data/registry/interconnect/regions/regional-routing.json",
    "data/registry/interconnect/routing/active-active-policy.json",
    "data/registry/interconnect/routing/route-priority.json",
    "data/registry/interconnect/analytics/call-quality.json",
    "data/registry/interconnect/analytics/latency-history.json",
    "data/registry/interconnect/analytics/availability-summary.json",
    "data/registry/interconnect/incidents/alert-rules.json",
    "data/registry/interconnect/incidents/incident-history.json"
]

def main():
    for item in FILES:
        path = BASE / item
        if not path.exists():
            print("Missing:", item)
            return 1
        json.loads(path.read_text())

    print("Scale operations validation passed")
    print(f"records checked: {len(FILES)}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
