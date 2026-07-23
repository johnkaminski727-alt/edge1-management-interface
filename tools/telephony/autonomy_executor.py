#!/usr/bin/env python3

import json
from pathlib import Path
from datetime import datetime


BASE = Path(__file__).resolve().parents[2]

POLICY = (
    BASE /
    "data/registry/interconnect/autonomy/policies.json"
)

RECOMMENDATIONS = (
    BASE /
    "data/registry/interconnect/intelligence/recommendations.json"
)

ACTIONS = (
    BASE /
    "data/registry/interconnect/autonomy/actions.json"
)


def main():

    policy = json.loads(
        POLICY.read_text()
    )

    recommendations = json.loads(
        RECOMMENDATIONS.read_text()
    )

    actions = json.loads(
        ACTIONS.read_text()
    )


    if not policy.get(
        "autonomy_enabled"
    ):

        print(
            "Autonomy disabled - recording recommendations only"
        )


    for item in recommendations.get(
        "recommendations",
        []
    ):

        actions.setdefault(
            "actions",
            []
        )

        actions["actions"].append(
            {
                "type": "recommendation",
                "target": item.get("peer"),
                "action": item.get("action"),
                "status": "pending_approval",
                "created": datetime.utcnow().isoformat() + "Z"
            }
        )


    ACTIONS.write_text(
        json.dumps(
            actions,
            indent=2
        )
    )


    print(
        "Autonomy executor completed"
    )

    print(
        f"actions recorded: {len(actions['actions'])}"
    )


if __name__ == "__main__":
    main()
