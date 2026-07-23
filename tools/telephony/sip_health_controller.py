#!/usr/bin/env python3

import json
import socket
import time
from pathlib import Path
from datetime import datetime

from lib.sip_message import (
    build_options_request,
    parse_response
)


BASE = Path(__file__).resolve().parents[2]

REGISTRY = (
    BASE /
    "data/registry/interconnect/interconnect-registry.json"
)

STATUS_FILE = (
    BASE /
    "data/registry/interconnect/status/peer-status.json"
)

HISTORY_FILE = (
    BASE /
    "data/registry/interconnect/status/sip-options-history.json"
)


def load(path):
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def save(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


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

        code = result.get("code")

        if code and 200 <= code < 300:
            state = "healthy"
        elif code and 400 <= code < 500:
            state = "degraded"
        else:
            state = "failed"

        return {
            "status": state,
            "response_code": code,
            "latency_ms": latency
        }

    except Exception as e:

        return {
            "status": "failed",
            "error": str(e)
        }


def main():

    with open(REGISTRY) as f:
        registry = json.load(f)

    status = load(STATUS_FILE)
    history = load(HISTORY_FILE)

    now = datetime.utcnow().isoformat() + "Z"

    for peer in registry.get("sip_peers", []):

        result = check_peer(peer)

        status.setdefault(
            "peers",
            {}
        )

        status["peers"][peer["id"]] = {
            "status": result["status"],
            "last_check": now,
            "sip_options": result
        }

        history.setdefault(
            "checks",
            []
        )

        history["checks"].append(
            {
                "peer": peer["id"],
                "timestamp": now,
                **result
            }
        )

        print(
            peer["id"],
            result
        )

    save(
        STATUS_FILE,
        status
    )

    save(
        HISTORY_FILE,
        history
    )


if __name__ == "__main__":
    main()
