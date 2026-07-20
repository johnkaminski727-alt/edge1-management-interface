#!/usr/bin/env python3

import json
import sys
from pathlib import Path
from datetime import datetime


BASE = Path(__file__).resolve().parents[2]

OUTPUT = (
    BASE /
    "data/registry/interconnect/provisioned"
)

REPORTS = (
    BASE /
    "reports/carriers"
)


def main():

    if len(sys.argv) < 3:
        print(
            "Usage: carrier_provision.py <carrier_id> <carrier_name>"
        )
        return 1


    carrier_id = sys.argv[1]
    carrier_name = sys.argv[2]


    OUTPUT.mkdir(
        parents=True,
        exist_ok=True
    )

    REPORTS.mkdir(
        parents=True,
        exist_ok=True
    )


    record = {
        "carrier_id": carrier_id,
        "name": carrier_name,
        "status": "planned",
        "created": datetime.utcnow().isoformat() + "Z",
        "sip": {
            "peer_id": f"{carrier_id}-peer",
            "transport": "tls",
            "codecs": [
                "PCMU",
                "PCMA"
            ]
        },
        "readiness": {
            "registry_complete": True,
            "sip_test_complete": False,
            "routing_complete": False
        }
    }


    output = (
        OUTPUT /
        f"{carrier_id}.json"
    )

    output.write_text(
        json.dumps(
            record,
            indent=2
        )
    )


    report_dir = (
        REPORTS /
        carrier_id
    )

    report_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    (
        report_dir /
        "carrier-profile.json"
    ).write_text(
        json.dumps(
            record,
            indent=2
        )
    )


    (
        report_dir /
        "acceptance-status.md"
    ).write_text(
        f"""# Carrier Acceptance Status

Carrier:
{carrier_name}

ID:
{carrier_id}

Status:
PLANNED

Registry:
Complete

SIP Testing:
Pending

Routing:
Pending
"""
    )


    print(
        "Carrier provisioned"
    )

    print(output)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
