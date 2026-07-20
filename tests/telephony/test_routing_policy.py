#!/usr/bin/env python3

import json
from pathlib import Path


BASE = Path(__file__).resolve().parents[2]

REGISTRY = BASE / "data/registry/interconnect/interconnect-registry.json"


def test_routes_have_destinations():

    with open(REGISTRY) as f:
        data = json.load(f)

    peers = {
        p["id"]
        for p in data["sip_peers"]
    }

    for route in data["routing_rules"]:
        assert route["destination"] in peers


def test_route_priorities():

    with open(REGISTRY) as f:
        data = json.load(f)

    for route in data["routing_rules"]:
        assert isinstance(
            route.get("priority"),
            int
        )


if __name__ == "__main__":

    test_routes_have_destinations()
    test_route_priorities()

    print("routing policy tests passed")
