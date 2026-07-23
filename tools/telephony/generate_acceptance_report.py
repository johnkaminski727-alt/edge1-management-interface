#!/usr/bin/env python3

import json
from pathlib import Path
from datetime import datetime


BASE = Path(__file__).resolve().parents[2]

REGISTRY = (
    BASE /
    "data/registry/interconnect/interconnect-registry.json"
)

STATUS = (
    BASE /
    "data/registry/interconnect/status/peer-status.json"
)

OUTPUT = (
    BASE /
    "reports/interconnect"
)


def load(path):

    if path.exists():
        with open(path) as f:
            return json.load(f)

    return {}


def main():

    OUTPUT.mkdir(
        parents=True,
        exist_ok=True
    )

    registry = load(REGISTRY)
    status = load(STATUS)

    peers = status.get(
        "peers",
        {}
    )


    report = f"""# Edge1 SIP Interconnect Acceptance Report

Generated:
{datetime.utcnow().isoformat()}Z


## Registry

Carriers:
{len(registry.get('carriers', []))}

SIP Peers:
{len(registry.get('sip_peers', []))}

Routes:
{len(registry.get('routing_rules', []))}


## SIP Testing

"""


    for peer, state in peers.items():

        report += f"""
Peer:
{peer}

Status:
{state.get('status')}

SIP OPTIONS:
{state.get('sip_options', {}).get('response_code')}

Latency:
{state.get('sip_options', {}).get('latency_ms')} ms

"""


    report += """
## Production Requirements

- Carrier agreement: Pending
- Production credentials: Pending
- Public signaling endpoint: Pending
- Emergency calling: Pending
- STIR/SHAKEN: Pending
"""


    output = (
        OUTPUT /
        "carrier-acceptance-report.md"
    )

    output.write_text(
        report
    )

    print(
        "Acceptance report generated"
    )
    print(output)


if __name__ == "__main__":
    main()
