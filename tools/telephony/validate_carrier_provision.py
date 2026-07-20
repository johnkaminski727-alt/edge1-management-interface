#!/usr/bin/env python3

import json
import sys
from pathlib import Path


BASE = Path(__file__).resolve().parents[2]

REGISTRY = (
    BASE /
    "data/registry/interconnect/interconnect-registry.json"
)


VALID_TRANSPORTS = {
    "udp",
    "tcp",
    "tls"
}


def main():

    with open(REGISTRY) as f:
        registry = json.load(f)


    carriers = {
        c["id"]: c
        for c in registry.get("carriers", [])
    }

    peers = {
        p["id"]: p
        for p in registry.get("sip_peers", [])
    }


    ok = True


    for carrier_id, carrier in carriers.items():

        print(
            f"Checking carrier: {carrier_id}"
        )


        carrier_peers = [
            p
            for p in peers.values()
            if p.get("carrier_id") == carrier_id
        ]


        if not carrier_peers:

            print(
                f"ERROR: no SIP peer for {carrier_id}"
            )

            ok = False
            continue


        for peer in carrier_peers:

            if peer.get("transport") not in VALID_TRANSPORTS:

                print(
                    f"ERROR: invalid transport "
                    f"{peer.get('transport')} "
                    f"for {peer['id']}"
                )

                ok = False


            if not peer.get("codecs"):

                print(
                    f"ERROR: no codecs for {peer['id']}"
                )

                ok = False


            if peer.get("endpoint") == "pending":

                print(
                    f"WARNING: endpoint pending "
                    f"for {peer['id']}"
                )


    if ok:

        print()
        print(
            "Carrier provisioning validation passed"
        )

        return 0


    print()
    print(
        "Carrier provisioning validation failed"
    )

    return 1


if __name__ == "__main__":
    sys.exit(main())
