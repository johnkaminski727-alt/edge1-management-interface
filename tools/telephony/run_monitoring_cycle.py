#!/usr/bin/env python3

import json
import subprocess
from pathlib import Path
from datetime import datetime


BASE = Path(__file__).resolve().parents[2]

HISTORY = (
    BASE /
    "data/registry/interconnect/monitoring/uptime-history.json"
)

REPORT = (
    BASE /
    "reports/operations/monitoring-summary.md"
)


def main():

    result = subprocess.run(
        [
            "python3",
            "tools/telephony/sip_health_controller.py"
        ],
        cwd=BASE,
        capture_output=True,
        text=True
    )


    history = {}

    if HISTORY.exists():

        history = json.loads(
            HISTORY.read_text()
        )


    history.setdefault(
        "checks",
        []
    )

    history["checks"].append(
        {
            "timestamp":
                datetime.utcnow().isoformat() + "Z",
            "result":
                "completed"
        }
    )


    HISTORY.write_text(
        json.dumps(
            history,
            indent=2
        )
    )


    REPORT.write_text(
        f"""# Edge1 SIP Monitoring Summary

Generated:
{datetime.utcnow().isoformat()}Z

Monitoring cycle:
completed

Health controller:
executed

History records:
{len(history['checks'])}
"""
    )


    print(
        "Monitoring cycle complete"
    )


if __name__ == "__main__":
    main()
