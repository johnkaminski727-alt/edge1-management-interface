#!/usr/bin/env python3

import socket
import time
import json
from pathlib import Path

from lib.sip_message import (
    build_options_request,
    parse_response
)


BASE = Path(__file__).resolve().parents[1]

REGISTRY = (
    BASE.parent /
    "data/registry/interconnect/interconnect-registry.json"
)


def check_peer(peer):

    endpoint = peer["endpoint"]
    port = 5060

    request = build_options_request(
        endpoint,
        port
    )

    start = time.time()

    try:
        sock = socket.socket(
            socket.AF_INET,
            socket.SOCK_DGRAM
        )

        sock.settimeout(2)

        sock.sendto(
            request.encode(),
            (endpoint, port)
        )

        data, _ = sock.recvfrom(4096)

        latency = round(
            (time.time() - start) * 1000,
            2
        )

        result = parse_response(
            data.decode(errors="ignore")
        )

        result["latency_ms"] = latency
        result["peer"] = peer["id"]

        return result

    except Exception as e:

        return {
            "peer": peer["id"],
            "status": "failed",
            "error": str(e)
        }


def main():

    with open(REGISTRY) as f:
        registry = json.load(f)

    print("SIP OPTIONS Monitor")
    print("==================")

    for peer in registry.get(
        "sip_peers",
        []
    ):

        print(
            check_peer(peer)
        )


if __name__ == "__main__":
    main()
