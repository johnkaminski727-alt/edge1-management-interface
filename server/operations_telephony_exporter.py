#!/usr/bin/env python3

from pathlib import Path
import urllib.request
import json
import datetime

OUTPUT = Path("/var/www/edge1-status/operations-telephony.json")


def main():

    result = {
        "generated_at":
            datetime.datetime.now(
                datetime.timezone.utc
            ).isoformat(),

        "available": False
    }

    try:
        with urllib.request.urlopen(
            "http://127.0.0.1:8096/api/telephony/status",
            timeout=5
        ) as response:
            data=json.loads(
                response.read()
            )

        result["available"]=True
        result["status"]=data

    except Exception as exc:
        result["error"]=str(exc)


    OUTPUT.write_text(
        json.dumps(result,indent=2)+"\n"
    )


if __name__=="__main__":
    main()
