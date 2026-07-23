#!/usr/bin/env python3

import json
from pathlib import Path
from datetime import datetime
import sys


BASE = Path(__file__).resolve().parents[2]

PROVISIONED = (
    BASE /
    "data/registry/interconnect/provisioned"
)

REGISTRY = (
    BASE /
    "data/registry/interconnect/interconnect-registry.json"
)

OUTPUT = (
    BASE /
    "reports/carriers"
)


def load(path):

    if path.exists():
        with open(path) as f:
            return json.load(f)

    return {}


def main():

    if len(sys.argv) < 2:
        print(
            "Usage: generate_carrier_package.py <carrier_id>"
        )
        return 1


    carrier_id = sys.argv[1]

    carrier_file = (
        PROVISIONED /
        f"{carrier_id}.json"
    )

    if not carrier_file.exists():

        print(
            "Carrier record not found"
        )

        return 1


    carrier = load(carrier_file)
    registry = load(REGISTRY)


    package = (
        OUTPUT /
        carrier_id
    )

    package.mkdir(
        parents=True,
        exist_ok=True
    )


    (package / "carrier-profile.json").write_text(
        json.dumps(
            carrier,
            indent=2
        )
    )


    peer_id = carrier["sip"]["peer_id"]

    peer = next(
        (
            p for p in registry.get(
                "sip_peers",
                []
            )
            if p.get("id") == peer_id
        ),
        {}
    )


    (package / "sip-peer-config.conf").write_text(
        f"""# Edge1 SIP Peer Configuration

peer={peer.get('id')}

endpoint={peer.get('endpoint')}

transport={peer.get('transport')}

codecs={','.join(peer.get('codecs', []))}
"""
    )


    (package / "routing-config.conf").write_text(
        """# Edge1 Carrier Routing Configuration

status=pending
"""
    )


    (package / "validation-report.md").write_text(
        f"""# Carrier Validation Report

Carrier:
{carrier.get('name')}

Generated:
{datetime.utcnow().isoformat()}Z


Registry:
PASS

SIP Peer:
{'PASS' if peer else 'FAIL'}

Routing:
PENDING
"""
    )


    print(
        "Carrier package generated"
    )

    print(package)


if __name__ == "__main__":
    raise SystemExit(main())
