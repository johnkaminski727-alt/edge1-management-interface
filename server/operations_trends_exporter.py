#!/usr/bin/env python3

from pathlib import Path
import json
import datetime


ROOT = Path("/var/www/edge1-status")

OUTPUT = ROOT / "operations-trends.json"


def load(name):
    try:
        return json.loads(
            (ROOT / name).read_text()
        )
    except Exception:
        return {}


def main():

    health = load(
        "operations-health.json"
    )

    timeline = load(
        "operations-timeline.json"
    )

    changes = load(
        "operations-changes.json"
    )

    reports = load(
        "reports/index.json"
    )


    events = timeline.get(
        "events",
        []
    )

    checks = health.get(
        "checks",
        []
    )

    warnings = [
        c.get("name")
        for c in checks
        if c.get("state") != "healthy"
    ]


    data = {

        "generated_at":
            datetime.datetime.now(
                datetime.timezone.utc
            ).isoformat(),

        "current": {

            "overall":
                health.get(
                    "overall",
                    "unknown"
                ),

            "warnings":
                warnings
        },


        "activity": {

            "recent_events":
                len(events),

            "recent_changes":
                len(
                    changes.get(
                        "recent_commits",
                        []
                    )
                ),

            "reports_available":
                reports.get(
                    "count",
                    0
                )
        },


        "categories": {

            "security":
                len([
                    e for e in events
                    if e.get("category")
                    == "security"
                ]),

            "network":
                len([
                    e for e in events
                    if e.get("category")
                    == "network"
                ]),

            "carrier":
                len([
                    e for e in events
                    if e.get("category")
                    == "carrier"
                ])
        }
    }


    OUTPUT.write_text(
        json.dumps(
            data,
            indent=2
        ) + "\n"
    )


if __name__ == "__main__":
    main()
