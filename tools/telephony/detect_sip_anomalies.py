#!/usr/bin/env python3

import json
from pathlib import Path
from datetime import datetime


BASE = Path(__file__).resolve().parents[2]

STATUS = (
    BASE /
    "data/registry/interconnect/status/peer-status.json"
)

ANOMALIES = (
    BASE /
    "data/registry/interconnect/intelligence/anomalies.json"
)

RECOMMENDATIONS = (
    BASE /
    "data/registry/interconnect/intelligence/recommendations.json"
)


def main():

    status = json.loads(
        STATUS.read_text()
    )

    anomalies = {
        "anomalies": []
    }

    recommendations = {
        "recommendations": []
    }


    for peer, state in status.get(
        "peers",
        {}
    ).items():

        if state.get("status") != "healthy":

            event = {
                "peer": peer,
                "type": "sip_peer_failure",
                "severity": "warning",
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }

            anomalies["anomalies"].append(
                event
            )

            recommendations["recommendations"].append(
                {
                    "peer": peer,
                    "action": "verify endpoint and carrier connectivity"
                }
            )


    ANOMALIES.write_text(
        json.dumps(
            anomalies,
            indent=2
        )
    )

    RECOMMENDATIONS.write_text(
        json.dumps(
            recommendations,
            indent=2
        )
    )


    print(
        "SIP anomaly detection complete"
    )

    print(
        f"anomalies detected: {len(anomalies['anomalies'])}"
    )


if __name__ == "__main__":
    main()
