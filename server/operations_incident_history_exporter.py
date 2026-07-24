#!/usr/bin/env python3

from pathlib import Path
import json
import datetime


SOURCE = Path(
    "/var/lib/wwcx-operations/incidents.json"
)

OUTPUT = Path(
    "/var/www/edge1-status/operations-incident-history.json"
)


def main():

    try:
        data=json.loads(
            SOURCE.read_text()
        )
    except Exception:
        data={}


    OUTPUT.write_text(
        json.dumps(
            {
                "generated_at":
                    datetime.datetime.now(
                        datetime.timezone.utc
                    ).isoformat(),

                "incidents":
                    data
            },
            indent=2
        )
        + "\n"
    )


if __name__=="__main__":
    main()
