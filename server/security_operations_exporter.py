#!/usr/bin/env python3
from pathlib import Path
import json
import datetime
import os

SOURCE = Path("/var/lib/bigbird/operations-center/latest.json")
OUTPUT = Path("/var/www/edge1-status/security-operations.json")


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def main():
    data = {}

    try:
        raw = json.loads(SOURCE.read_text())
        security = raw.get("security", {})
        if not isinstance(security, dict):
            security = {}

        evidence_dir = Path("/var/lib/edge1-operations-api/evidence/security")
        evidence = []

        if evidence_dir.exists():
            for item in sorted(
                evidence_dir.glob("*.json"),
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )[:5]:
                evidence.append({
                    "file": item.name,
                    "modified": datetime.datetime.fromtimestamp(
                        item.stat().st_mtime,
                        datetime.timezone.utc
                    ).isoformat()
                })

        data = {
            "generated_at": raw.get("generated_at"),
            "available": bool(security.get("available", False)),
            "engine": security.get("engine", {}),
            "logs": security.get("logs", {}),
            "health": security.get("health", {}),
            "counts": security.get("counts", {}),
            "recent_alerts": security.get("recent_alerts", [])[:50],
            "evidence": evidence,
            "advisories": [
                "Runtime configuration override detected: wwcx-runtime.yaml defines the active af-packet sensor interface (wg0). This is expected BigBird deployment behavior."
            ]
        }

    except Exception as exc:
        data = {
            "generated_at": utc_now(),
            "available": False,
            "error": str(exc),
            "engine": {},
            "logs": {},
            "health": {
                "status": "error",
                "warnings": [str(exc)]
            },
            "counts": {},
            "recent_alerts": [],
        }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    tmp = OUTPUT.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False
        ) + "\n"
    )

    os.chmod(tmp, 0o644)
    tmp.replace(OUTPUT)

    print(json.dumps({
        "ok": True,
        "output": str(OUTPUT)
    }))


if __name__ == "__main__":
    main()
