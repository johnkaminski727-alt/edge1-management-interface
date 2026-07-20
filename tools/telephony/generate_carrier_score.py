#!/usr/bin/env python3

import json
from pathlib import Path


BASE = Path(__file__).resolve().parents[2]

STATUS = (
    BASE /
    "data/registry/interconnect/status/peer-status.json"
)

OUTPUT = (
    BASE /
    "data/registry/interconnect/intelligence/scoring.json"
)


def main():

    status = json.loads(
        STATUS.read_text()
    )

    scores = {
        "carriers": []
    }


    for peer, state in status.get(
        "peers",
        {}
    ).items():

        healthy = (
            state.get("status")
            == "healthy"
        )

        score = 95 if healthy else 40


        scores["carriers"].append(
            {
                "peer": peer,
                "score": score,
                "health_rating":
                    "excellent"
                    if healthy
                    else "degraded"
            }
        )


    OUTPUT.write_text(
        json.dumps(
            scores,
            indent=2
        )
    )


    print(
        "Carrier scoring complete"
    )

    print(
        f"scores generated: {len(scores['carriers'])}"
    )


if __name__ == "__main__":
    main()
