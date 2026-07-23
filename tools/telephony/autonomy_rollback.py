#!/usr/bin/env python3

import json
from pathlib import Path
from datetime import datetime


BASE = Path(__file__).resolve().parents[2]

ROLLBACK = (
    BASE /
    "data/registry/interconnect/autonomy/rollback-history.json"
)


def main():

    history = json.loads(
        ROLLBACK.read_text()
    )


    history.setdefault(
        "rollbacks",
        []
    )


    history["rollbacks"].append(
        {
            "event": "rollback_checkpoint_created",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "status": "ready"
        }
    )


    ROLLBACK.write_text(
        json.dumps(
            history,
            indent=2
        )
    )


    print(
        "Rollback checkpoint created"
    )

    print(
        f"rollback records: {len(history['rollbacks'])}"
    )


if __name__ == "__main__":
    main()
