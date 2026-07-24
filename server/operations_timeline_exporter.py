#!/usr/bin/env python3

from pathlib import Path
import json
import datetime

OUTPUT = Path("/var/www/edge1-status/operations-timeline.json")

EVENTS = []


def add_event(source, title, timestamp, detail):
    if timestamp:
        EVENTS.append({
            "source": source,
            "title": title,
            "timestamp": timestamp,
            "detail": detail
        })


def main():

    security = Path("/var/www/edge1-status/security-operations.json")
    wallet = Path("/var/www/edge1-status/bitcoin-wallet.json")
    mining = Path("/var/www/edge1-status/bitcoin-mining.json")

    if security.exists():
        data=json.loads(security.read_text())

        add_event(
            "security",
            "Security telemetry refreshed",
            data.get("generated_at"),
            f"Health: {data.get('health',{}).get('status','unknown')}"
        )

        for item in data.get("evidence",[])[:3]:
            add_event(
                "security",
                "Security validation evidence",
                item.get("modified"),
                item.get("file","")
            )

    if wallet.exists():
        data=json.loads(wallet.read_text())

        add_event(
            "bitcoin",
            "Bitcoin wallet telemetry refreshed",
            data.get("generated_at"),
            f"Wallet state: {data.get('service',{}).get('state','unknown')}"
        )

    if mining.exists():
        data=json.loads(mining.read_text())

        add_event(
            "mining",
            "Mining telemetry refreshed",
            data.get("generated_at"),
            f"Mode: {data.get('mode','unknown')}"
        )


    EVENTS.sort(
        key=lambda x:x.get("timestamp",""),
        reverse=True
    )

    OUTPUT.write_text(
        json.dumps(
            {
                "generated_at":
                    datetime.datetime.now(
                        datetime.timezone.utc
                    ).isoformat(),
                "events": EVENTS[:20]
            },
            indent=2
        )+"\n"
    )

    print("Timeline exported")


if __name__ == "__main__":
    main()
