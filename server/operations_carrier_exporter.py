#!/usr/bin/env python3

from pathlib import Path
import urllib.request
import json
import datetime

OUTPUT = Path("/var/www/edge1-status/operations-carrier.json")


def fetch(url):

    try:
        with urllib.request.urlopen(
            url,
            timeout=5
        ) as response:
            return json.loads(
                response.read()
            )

    except Exception as exc:
        return {
            "available": False,
            "error": str(exc)
        }


def main():

    telephony = fetch(
        "http://127.0.0.1:8096/api/telephony/status"
    )

    numbering = fetch(
        "http://127.0.0.1:8093/healthz"
    )


    data = {
        "generated_at":
            datetime.datetime.now(
                datetime.timezone.utc
            ).isoformat(),

        "telephony": telephony,

        "numbering": numbering,

        "carrier_readiness": {
            "status":
                "monitoring",
            "note":
                "Carrier activation requires explicit operational approval."
        }
    }


    OUTPUT.write_text(
        json.dumps(
            data,
            indent=2
        )+"\n"
    )


if __name__ == "__main__":
    main()
