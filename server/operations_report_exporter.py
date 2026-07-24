#!/usr/bin/env python3

from pathlib import Path
import json
import datetime


ROOT = Path("/var/www/edge1-status")
REPORT_DIR = ROOT / "reports"


def load(name):
    try:
        return json.loads((ROOT / name).read_text())
    except Exception:
        return {}


def main():

    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    now = datetime.datetime.now(
        datetime.timezone.utc
    )

    stamp = now.strftime("%Y%m%d-%H%M%S")

    health = load("operations-health.json")
    summary = load("daily-summary.json")
    timeline = load("operations-timeline.json")
    changes = load("operations-changes.json")
    automation = load("operations-automation.json")
    correlation = load("operations-correlation.json")


    report = {
        "generated_at": now.isoformat(),
        "health": health,
        "summary": summary,
        "timeline": timeline,
        "changes": changes,
        "automation": automation,
        "correlation": correlation
    }


    json_path = REPORT_DIR / (
        f"operations-report-{stamp}.json"
    )

    html_path = REPORT_DIR / (
        f"operations-report-{stamp}.html"
    )


    json_path.write_text(
        json.dumps(report, indent=2) + "\n"
    )


    html_path.write_text(
f"""
<!doctype html>
<html>
<head>
<title>WW.CX Edge1 Operations Report</title>
<style>
body {{
font-family:system-ui;
background:#0b1015;
color:#eee;
padding:30px;
}}
.panel {{
background:#151c22;
border:1px solid #444;
border-radius:12px;
padding:18px;
margin-bottom:18px;
}}
</style>
</head>

<body>

<h1>WW.CX Edge1 Operations Report</h1>

<div class="panel">
<h2>Overall Health</h2>
<pre>{json.dumps(health,indent=2)}</pre>
</div>

<div class="panel">
<h2>Recent Changes</h2>
<pre>{json.dumps(changes,indent=2)}</pre>
</div>

<div class="panel">
<h2>Incident Context</h2>
<pre>{json.dumps(correlation,indent=2)}</pre>
</div>

</body>
</html>
"""
    )


    reports = sorted(
        REPORT_DIR.glob("operations-report-*.html"),
        key=lambda x: x.stat().st_mtime,
        reverse=True
    )

    index = {
        "generated_at": now.isoformat(),
        "count": len(reports),
        "latest": reports[0].name if reports else ""
    }

    (REPORT_DIR / "index.json").write_text(
        json.dumps(index, indent=2) + "\n"
    )

    print(html_path)


if __name__ == "__main__":
    main()
