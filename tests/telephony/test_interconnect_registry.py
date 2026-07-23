#!/usr/bin/env python3

import json
from pathlib import Path


BASE = Path(__file__).resolve().parents[2]

REGISTRY = BASE / "data/registry/interconnect/interconnect-registry.json"


def test_registry_exists():

    assert REGISTRY.exists()


def test_registry_structure():

    with open(REGISTRY) as f:
        data = json.load(f)

    assert "carriers" in data
    assert "sip_peers" in data
    assert "routing_rules" in data


def test_peer_references_carrier():

    with open(REGISTRY) as f:
        data = json.load(f)

    carriers = {
        c["id"]
        for c in data["carriers"]
    }

    for peer in data["sip_peers"]:
        assert peer["carrier_id"] in carriers


if __name__ == "__main__":
    test_registry_exists()
    test_registry_structure()
    test_peer_references_carrier()
    print("interconnect registry tests passed")
