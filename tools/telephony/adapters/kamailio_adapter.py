#!/usr/bin/env python3

import json
from pathlib import Path
from datetime import datetime


BASE = Path(__file__).resolve().parents[3]

REGISTRY = BASE / "data/registry/interconnect/interconnect-registry.json"

OUTPUT = BASE / "generated/telephony/kamailio"


def main():

    OUTPUT.mkdir(parents=True, exist_ok=True)

    with open(REGISTRY) as f:
        registry = json.load(f)


    with open(OUTPUT / "kamailio-peers.cfg", "w") as f:

        f.write("# Edge1 Generated Kamailio Peer Configuration\n")
        f.write(
            "# Generated "
            + datetime.utcnow().isoformat()
            + "Z\n\n"
        )

        for peer in registry.get("sip_peers", []):

            f.write(
                f"# Peer: {peer['id']}\n"
            )

            f.write(
                "dispatcher.add_peer("
                f"'{peer['endpoint']}'"
                ")\n"
            )

            f.write(
                f"# transport={peer['transport']}\n\n"
            )


    with open(OUTPUT / "kamailio-routing.cfg", "w") as f:

        f.write("# Edge1 Generated Kamailio Routing\n\n")

        for route in registry.get("routing_rules", []):

            f.write(
                f"# Route: {route['id']}\n"
            )

            f.write(
                f"# Match: {route['match']}\n"
            )

            f.write(
                f"# Destination: {route['destination']}\n\n"
            )


    print("Kamailio adapter output generated")
    print(OUTPUT)


if __name__ == "__main__":
    main()
