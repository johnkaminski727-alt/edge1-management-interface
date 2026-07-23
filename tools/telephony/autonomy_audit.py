#!/usr/bin/env python3

import json
from pathlib import Path
from datetime import datetime


BASE = Path(__file__).resolve().parents[2]

ACTIONS = (
    BASE /
    "data/registry/interconnect/autonomy/actions.json"
)

HISTORY = (
    BASE /
    "data/registry/interconnect/autonomy/execution-history.json"
)


def main():

    actions = json.loads(
        ACTIONS.read_text()
    )

    history = json.loads(
        HISTORY.read_text()
    )


    history.setdefault(
        "executions",
        []
    )


    for action in actions.get(
        "actions",
        []
    ):

        history["executions"].append(
            {
                "target": action.get("target"),
                "action": action.get("action"),
                "state": action.get("status"),
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
        )


    HISTORY.write_text(
        json.dumps(
            history,
            indent=2
        )
    )


    print(
        "Autonomy audit updated"
    )

    print(
        f"execution records: {len(history['executions'])}"
    )


if __name__ == "__main__":
    main()
