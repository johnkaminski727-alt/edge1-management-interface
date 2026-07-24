#!/usr/bin/env python3

from pathlib import Path
import json
import datetime

OUTPUT = Path("/var/www/edge1-status/operations-timeline.json")

EVENTS = []


def add_event(category, severity, state, title, timestamp, detail, recommendation):
    if timestamp:
        EVENTS.append({
            "category": category,
            "severity": severity,
            "state": state,
            "title": title,
            "timestamp": timestamp,
            "detail": detail,
            "recommendation": recommendation
        })


def main():

    security = Path("/var/www/edge1-status/security-operations.json")
    wallet = Path("/var/www/edge1-status/bitcoin-wallet.json")
    mining = Path("/var/www/edge1-status/bitcoin-mining.json")
    network = Path("/var/www/edge1-status/operations-network.json")
    carrier = Path("/var/www/edge1-status/operations-carrier.json")

    if security.exists():
        data=json.loads(security.read_text())

        add_event(
            "security",
            "warning" if data.get("health",{}).get("status") != "healthy" else "info",
            "current",
            "Security telemetry refreshed",
            data.get("generated_at"),
            f"Health: {data.get('health',{}).get('status','unknown')}",
            "Review warnings if present."
        )

        for item in data.get("evidence",[])[:3]:
            add_event(
                "security",
                "info",
                "historical",
                "Security validation evidence",
                item.get("modified"),
                item.get("file",""),
                "No action required."
            )

    if wallet.exists():
        data=json.loads(wallet.read_text())

        add_event(
            "bitcoin",
            "info",
            "current",
            "Bitcoin wallet telemetry refreshed",
            data.get("generated_at"),
            f"Wallet state: {data.get('service',{}).get('state','unknown')}",
            "Continue monitoring."
        )

    if mining.exists():
        data=json.loads(mining.read_text())

        add_event(
            "mining",
            "warning" if data.get("warnings") else "info",
            "current",
            "Mining telemetry refreshed",
            data.get("generated_at"),
            f"Mode: {data.get('mode','unknown')}",
            "Review mining warnings if present."
        )


    if network.exists():
        data=json.loads(network.read_text())

        add_event(
            "network",
            "info",
            "current",
            "Network posture refreshed",
            data.get("generated_at"),
            f"Interfaces: {len(data.get('interfaces', []))}",
            "No action required."
        )


    if carrier.exists():
        data=json.loads(carrier.read_text())

        readiness = data.get(
            "carrier_readiness",
            {}
        )

        add_event(
            "carrier",
            "warning"
            if data.get("telephony",{}).get("overall_status") == "degraded"
            else "info",
            "current",
            "Carrier posture refreshed",
            data.get("generated_at"),
            f"Readiness: {readiness.get('status','unknown')}",
            readiness.get(
                "note",
                "No action required."
            )
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
