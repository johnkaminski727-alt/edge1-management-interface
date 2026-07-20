#!/usr/bin/env python3

import json
from pathlib import Path


BASE = Path(__file__).resolve().parents[2]

ANOMALIES = (
    BASE /
    "data/registry/interconnect/intelligence/anomalies.json"
)

OUTPUT = (
    BASE /
    "data/registry/interconnect/intelligence/forecasts.json"
)


def main():

    anomalies = json.loads(
        ANOMALIES.read_text()
    )

    forecast = {
        "forecasts": []
    }


    failed_peers = {
        item["peer"]
        for item in anomalies.get(
            "anomalies",
            []
        )
    }


    for peer in failed_peers:

        forecast["forecasts"].append(
            {
                "peer": peer,
                "forecast": "degraded",
                "risk": "medium",
                "reason": "recent SIP failure detected"
            }
        )


    if not forecast["forecasts"]:

        forecast["forecasts"].append(
            {
                "forecast": "stable",
                "risk": "low"
            }
        )


    OUTPUT.write_text(
        json.dumps(
            forecast,
            indent=2
        )
    )


    print(
        "Operations forecast generated"
    )

    print(
        f"forecasts: {len(forecast['forecasts'])}"
    )


if __name__ == "__main__":
    main()
