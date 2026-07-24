#!/usr/bin/env python3

from pathlib import Path
import json
import datetime

REPORTS = Path("/var/www/edge1-status/reports")
OUTPUT = REPORTS / "index.json"


def latest(pattern):
    files = [
        x for x in REPORTS.glob(pattern)
        if x.name != "index.json"
    ]

    files = sorted(
        files,
        key=lambda x: x.stat().st_mtime,
        reverse=True
    )

    return files[0].name if files else ""


def main():

    REPORTS.mkdir(
        parents=True,
        exist_ok=True
    )

    reports = {
        "generated_at":
            datetime.datetime.now(
                datetime.timezone.utc
            ).isoformat(),

        "latest_html":
            latest("*.html"),

        "latest_json":
            latest("*.json"),

        "latest_pdf":
            latest("*.pdf"),

        "count":
            len(list(REPORTS.glob("operations-report-*")))
    }


    OUTPUT.write_text(
        json.dumps(
            reports,
            indent=2
        ) + "\n"
    )


if __name__ == "__main__":
    main()
