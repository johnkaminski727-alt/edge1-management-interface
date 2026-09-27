#!/usr/bin/python3
"""Publish sanitized CrowdSec events without raw identities."""

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

DEST = Path("/var/www/edge1-status/security-correlation.json")
TESTS = {
    "edge1-live-update-test",
    "edge1-timeout-sync-test",
    "edge1-automerge-test",
    "edge1-synchronization-test",
}

def main():
    cli = shutil.which("cscli")
    if not cli:
        raise RuntimeError("CrowdSec CLI unavailable")

    result = subprocess.run(
        [cli, "alerts", "list", "-o", "json"],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    alerts = json.loads(result.stdout)
    if not isinstance(alerts, list):
        raise ValueError("Unexpected CrowdSec alert format")

    events = []
    excluded = 0

    for alert in alerts[:200]:
        if not isinstance(alert, dict):
            continue

        scenario = alert.get("scenario")
        simulated = alert.get("simulated")

        if scenario in TESTS or simulated is True:
            excluded += 1
            continue

        if not isinstance(scenario, str):
            continue

        # Include only ordinary CrowdSec scenario identifiers.
        if not re.fullmatch(
            r"[A-Za-z0-9_./-]{1,100}", scenario
        ):
            continue

        raw_time = alert.get("created_at")
        if not isinstance(raw_time, str):
            continue

        try:
            timestamp = dt.datetime.fromisoformat(
                raw_time.replace("Z", "+00:00")
            )
            if timestamp.tzinfo is None:
                continue
        except ValueError:
            continue

        material = (
            str(alert.get("id", "")) + "|" +
            scenario + "|" + raw_time
        )
        event_id = hashlib.sha256(
            material.encode()
        ).hexdigest()[:20]

        events.append({
            "id": event_id,
            "category": "crowdsec",
            "timestamp": timestamp.isoformat(),
            "severity": "unknown",
            "title": "CrowdSec: " + scenario,
            "source": None,
            "destination": None,
            "domain": None,
            "detail": (
                "CrowdSec alert recorded. "
                "Endpoint identities intentionally omitted."
            ),
            "recommendation": (
                "Review restricted CrowdSec evidence "
                "before taking action."
            ),
        })

    events.sort(
        key=lambda event: event["timestamp"],
        reverse=True,
    )

    now = dt.datetime.now(
        dt.timezone.utc
    ).isoformat()

    snapshot = {
        "schema_version": "1.0",
        "generated_at": now,
        "read_only": True,
        "traffic_controls_changed": False,
        "source_status": {
            "crowdsec": {
                "available": True,
                "detail": (
                    "Current sanitized CrowdSec alert listing"
                ),
                "modified_at": now,
            },
        },
        "summary": {
            "event_count": len(events),
            "correlation_count": 0,
            "high_confidence_count": 0,
            "category_counts": {
                "crowdsec": len(events),
            },
            "available_source_count": 1,
            "source_count": 1,
        },
        "network_context": {
            "resolver_observed": False,
        },
        "reputation_context": {
            "configured_entries": 0,
        },
        "events": events,
        "correlations": [],
        "warnings": [
            "Independent event-source correlation "
            "is not connected."
        ],
        "limitations": [
            "Only alerts returned by the current "
            "CrowdSec CLI listing are included.",
            "Known deployment tests and simulated "
            "alerts are excluded.",
            "Endpoint identities and raw event "
            "payloads are omitted.",
            "No independent correlations are asserted.",
            "A fresh snapshot does not imply "
            "that its events occurred recently.",
        ],
    }

    fd, temporary = tempfile.mkstemp(
        prefix=".security-correlation-",
        dir=str(DEST.parent),
    )

    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(snapshot, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o644)
        os.replace(temporary, DEST)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

    print(
        "Sanitized events:", len(events),
        "| Excluded test/simulated:", excluded,
        "| Established correlations: 0"
    )

if __name__ == "__main__":
    main()
