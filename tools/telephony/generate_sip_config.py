#!/usr/bin/env python3

import json
from pathlib import Path
from datetime import datetime


BASE = Path(__file__).resolve().parents[2]

REGISTRY = BASE / "data/registry/interconnect/interconnect-registry.json"
OUTPUT = BASE / "generated/telephony"


def main():

    OUTPUT.mkdir(parents=True, exist_ok=True)

    with open(REGISTRY) as f:
        registry = json.load(f)


    peers = registry.get("sip_peers", [])
    routes = registry.get("routing_rules", [])


    with open(OUTPUT / "peers.conf", "w") as f:

        f.write("# Edge1 Generated SIP Peers\n")
        f.write(
            "# Generated: "
            + datetime.utcnow().isoformat()
            + "Z\n\n"
        )

        for peer in peers:
            f.write(
                f"[peer:{peer['id']}]\n"
            )
            f.write(
                f"endpoint={peer['endpoint']}\n"
            )
            f.write(
                f"transport={peer['transport']}\n\n"
            )


    with open(OUTPUT / "routing.conf", "w") as f:

        f.write("# Edge1 Generated Routing\n\n")

        for route in routes:
            f.write(
                f"[route:{route['id']}]\n"
            )
            f.write(
                f"match={route['match']}\n"
            )
            f.write(
                f"destination={route['destination']}\n"
            )
            f.write(
                f"priority={route.get('priority',0)}\n\n"
            )


    with open(OUTPUT / "security.conf", "w") as f:

        f.write("# Edge1 SIP Security Baseline\n")
        f.write("tls=planned\n")
        f.write("acl=enabled\n")


    print("SIP configuration generated")
    print(OUTPUT)


if __name__ == "__main__":
    main()
