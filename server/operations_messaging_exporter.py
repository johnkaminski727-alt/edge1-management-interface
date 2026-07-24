#!/usr/bin/env python3

from pathlib import Path
import urllib.request
import json
import datetime

OUTPUT = Path("/var/www/edge1-status/operations-messaging.json")


def main():

    result={
        "generated_at":
            datetime.datetime.now(
                datetime.timezone.utc
            ).isoformat(),
        "available":False
    }

    try:
        with urllib.request.urlopen(
            "http://127.0.0.1:58080/healthz",
            timeout=5
        ) as response:
            result["status"]=json.loads(
                response.read()
            )
            result["available"]=True

    except Exception as exc:
        result["error"]=str(exc)

    OUTPUT.write_text(
        json.dumps(result,indent=2)+"\n"
    )


if __name__=="__main__":
    main()
