#!/usr/bin/env python3

import json
import sys
from pathlib import Path


BASE = Path(__file__).resolve().parents[2]

REGISTRY = BASE / "data/registry/interconnect/interconnect-registry.json"


VALID_TRANSPORTS = {
    "udp",
    "tcp",
    "tls"
}


def fail(message):
    print(f"ERROR: {message}")
    return False


def main():

    if not REGISTRY.exists():
        return fail(f"Missing registry: {REGISTRY}")

    with open(REGISTRY) as f:
        data = json.load(f)

    carriers = {
        c["id"]
        for c in data.get("carriers", [])
        if "id" in c
    }

    ok = True


    for peer in data.get("sip_peers", []):

        required = [
            "id",
            "carrier_id",
            "endpoint",
            "transport"
        ]

        for field in required:
            if field not in peer:
                ok = fail(
                    f"SIP peer missing field: {field}"
                )


        if peer.get("transport") not in VALID_TRANSPORTS:
            ok = fail(
                f"Invalid transport for {peer.get('id')}: "
                f"{peer.get('transport')}"
            )


        if peer.get("carrier_id") not in carriers:
            ok = fail(
                f"SIP peer references unknown carrier: "
                f"{peer.get('carrier_id')}"
            )


    for route in data.get("routing_rules", []):

        if "priority" in route:
            if not isinstance(route["priority"], int):
                ok = fail(
                    f"Invalid route priority: {route['id']}"
                )


    if ok:
        print("SIP interconnect registry validation passed")
        print(
            f"carriers: {len(data.get('carriers', []))}"
        )
        print(
            f"sip peers: {len(data.get('sip_peers', []))}"
        )
        print(
            f"routing rules: {len(data.get('routing_rules', []))}"
        )
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
