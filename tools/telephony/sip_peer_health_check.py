#!/usr/bin/env python3

import json
import socket
from pathlib import Path


BASE = Path(__file__).resolve().parents[2]

REGISTRY = BASE / "data/registry/interconnect/interconnect-registry.json"


def check_endpoint(endpoint, port=5060):

    try:
        socket.gethostbyname(endpoint)

        return {
            "status": "reachable",
            "endpoint": endpoint,
            "port": port
        }

    except Exception as e:

        return {
            "status": "unreachable",
            "endpoint": endpoint,
            "error": str(e)
        }


def main():

    with open(REGISTRY) as f:
        data = json.load(f)

    print("SIP Peer Health Report")
    print("=====================")

    for peer in data.get("sip_peers", []):

        result = check_endpoint(
            peer["endpoint"]
        )

        print(
            f"{peer['id']}: "
            f"{result['status']}"
        )


if __name__ == "__main__":
    main()
