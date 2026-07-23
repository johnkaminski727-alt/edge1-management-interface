#!/usr/bin/env python3

import json
from pathlib import Path
from datetime import datetime


BASE = Path(__file__).resolve().parents[2]

REGISTRY = BASE / "data/registry/interconnect/interconnect-registry.json"
REPORT_DIR = BASE / "reports"


def main():

    REPORT_DIR.mkdir(exist_ok=True)

    with open(REGISTRY) as f:
        data = json.load(f)

    report = {
        "generated": datetime.utcnow().isoformat() + "Z",
        "platform": "Edge1 SIP Interconnect",
        "summary": {
            "carriers": len(data.get("carriers", [])),
            "sip_peers": len(data.get("sip_peers", [])),
            "routing_rules": len(data.get("routing_rules", []))
        },
        "production_requirements": {
            "carrier_agreement": False,
            "sip_credentials": False,
            "public_signaling_endpoint": False,
            "emergency_calling": False,
            "stir_shaken": False
        }
    }


    with open(
        REPORT_DIR / "interconnect-readiness.json",
        "w"
    ) as f:
        json.dump(
            report,
            f,
            indent=2
        )


    markdown = f"""# Edge1 SIP Interconnect Readiness

Generated:
{report['generated']}

## Current Registry

- Carriers: {report['summary']['carriers']}
- SIP Peers: {report['summary']['sip_peers']}
- Routing Rules: {report['summary']['routing_rules']}

## Production Requirements

- Carrier agreement: Pending
- SIP credentials: Pending
- Public signaling endpoint: Pending
- Emergency calling: Pending
- STIR/SHAKEN: Pending
"""

    with open(
        REPORT_DIR / "interconnect-readiness.md",
        "w"
    ) as f:
        f.write(markdown)


    print("Interconnect readiness report generated")
    print(REPORT_DIR / "interconnect-readiness.json")
    print(REPORT_DIR / "interconnect-readiness.md")


if __name__ == "__main__":
    main()
