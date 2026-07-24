#!/usr/bin/env python3

from pathlib import Path
import json
import datetime

from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer
)

from reportlab.lib.styles import getSampleStyleSheet


ROOT = Path("/var/www/edge1-status")
REPORTS = ROOT / "reports"


def load(name):
    try:
        return json.loads(
            (ROOT / name).read_text()
        )
    except Exception:
        return {}


def main():

    REPORTS.mkdir(
        parents=True,
        exist_ok=True
    )

    now = datetime.datetime.now(
        datetime.timezone.utc
    )

    stamp = now.strftime("%Y%m%d-%H%M%S")

    output = REPORTS / (
        f"operations-report-{stamp}.pdf"
    )

    health = load(
        "operations-health.json"
    )

    summary = load(
        "daily-summary.json"
    )

    correlation = load(
        "operations-correlation.json"
    )

    changes = load(
        "operations-changes.json"
    )

    incidents = load(
        "operations-incidents.json"
    )

    doc = SimpleDocTemplate(
        str(output)
    )

    styles = getSampleStyleSheet()

    content = []

    content.append(
        Paragraph(
            "WW.CX Edge1 Operations Report",
            styles["Title"]
        )
    )

    content.append(
        Spacer(1, 12)
    )

    content.append(
        Paragraph(
            f"Generated: {now.isoformat()}",
            styles["Normal"]
        )
    )


    sections = [
        ("Overall Health", health),
        ("Daily Summary", summary),
        ("Incident Context", correlation),
        ("Recent Changes", changes),
        ("Active Incidents", incidents)
    ]

    for title, data in sections:

        content.append(
            Paragraph(
                title,
                styles["Heading2"]
            )
        )

        content.append(
            Paragraph(
                json.dumps(
                    data,
                    indent=2
                ).replace("\n","<br/>"),
                styles["Code"]
            )
        )

        content.append(
            Spacer(1,12)
        )


    doc.build(content)

    print(output)


if __name__ == "__main__":
    main()
