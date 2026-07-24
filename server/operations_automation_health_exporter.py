#!/usr/bin/env python3

from pathlib import Path
import json
import subprocess
import datetime

OUTPUT = Path("/var/www/edge1-status/operations-automation.json")

TIMERS = [
    "wwcx-security-operations.timer",
    "wwcx-operations-health.timer",
    "wwcx-operations-timeline.timer",
    "wwcx-operations-summary.timer",
]


def timer_state(name):
    result = subprocess.run(
        [
            "systemctl",
            "show",
            name,
            "-p",
            "ActiveState",
            "-p",
            "NextElapseUSecRealtime",
            "--value",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    values = result.stdout.splitlines()

    return {
        "name": name,
        "state": values[0] if values else "unknown",
        "next_run": values[1] if len(values) > 1 else ""
    }


def main():

    data = {
        "generated_at": datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat(),
        "timers": [
            timer_state(timer)
            for timer in TIMERS
        ]
    }

    OUTPUT.write_text(
        json.dumps(data, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
