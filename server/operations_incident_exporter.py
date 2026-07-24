#!/usr/bin/env python3

from pathlib import Path
import json
import datetime

ROOT = Path("/var/www/edge1-status")

OUTPUT = ROOT / "operations-incidents.json"


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


    incidents = []

    for check in health.get("checks", []):

        if check.get("state") != "healthy":

            incidents.append({

                "id":
                    "INC-"
                    + datetime.datetime.now(
                        datetime.timezone.utc
                    ).strftime("%Y%m%d")
                    + "-"
                    + check.get(
                        "name",
                        "unknown"
                    ).lower(),

                "component":
                    check.get("name"),

                "severity":
                    check.get(
                        "state",
                        "unknown"
                    ),

                "status":
                    "monitoring",

                "detail":
                    check.get(
                        "detail",
                        ""
                    ),

                "recommendation":
                    check.get(
                        "recommendation",
                        ""
                    ),

                "detected_at":
                    check.get(
                        "timestamp"
                    )
                    or datetime.datetime.now(
                        datetime.timezone.utc
                    ).isoformat()
            })


    data = {

        "generated_at":
            datetime.datetime.now(
                datetime.timezone.utc
            ).isoformat(),

        "active_incidents":
            incidents,

        "recent_events":
            timeline.get(
                "events",
                []
            )[:10]
    }


    OUTPUT.write_text(
        json.dumps(
            data,
            indent=2
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
