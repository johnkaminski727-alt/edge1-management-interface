#!/usr/bin/env python3

from pathlib import Path
import json
import datetime

ROOT = Path("/var/www/edge1-status")

OUTPUT = ROOT / "operations-correlation.json"


def load(name):
    try:
        return json.loads((ROOT / name).read_text())
    except Exception:
        return {}


def main():

    health = load("operations-health.json")
    changes = load("operations-changes.json")
    timeline = load("operations-timeline.json")

    active_conditions = []

    for check in health.get("checks", []):
        if check.get("state") != "healthy":
            active_conditions.append({
                "component": check.get("name"),
                "state": check.get("state"),
                "reason_code": check.get("reason_code",""),
                "detail": check.get("detail"),
                "recommendation": check.get("recommendation","")
            })


    recent_changes = changes.get("recent_commits", [])[:5]

    correlation = {
        "generated_at":
            datetime.datetime.now(
                datetime.timezone.utc
            ).isoformat(),

        "conditions": active_conditions,

        "recent_changes": recent_changes,

        "recent_events":
            timeline.get("events",[])[:5],

        "assessment":
            "Review recent changes alongside active conditions. No automatic causation is assumed."
    }


    OUTPUT.write_text(
        json.dumps(correlation, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
