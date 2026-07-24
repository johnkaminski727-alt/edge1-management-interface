#!/usr/bin/env python3

from pathlib import Path
import json
import datetime

ROOT = Path("/var/www/edge1-status")

OUTPUT_JSON = ROOT / "daily-summary.json"
OUTPUT_HTML = ROOT / "daily-summary.html"


def load(name):
    try:
        return json.loads((ROOT / name).read_text())
    except Exception:
        return {}


def main():

    health = load("operations-health.json")
    security = load("security-operations.json")
    wallet = load("bitcoin-wallet.json")
    mining = load("bitcoin-mining.json")
    timeline = load("operations-timeline.json")

    checks = health.get("checks", [])

    summary = {
        "generated_at":
            datetime.datetime.now(
                datetime.timezone.utc
            ).isoformat(),

        "overall":
            health.get("overall", "unknown"),

        "checks": checks,

        "recent_events":
            timeline.get("events", [])[:10],

        "security": {
            "state":
                security.get("health",{}).get("status"),
            "alerts":
                len(security.get("recent_alerts",[])),
            "version":
                security.get("engine",{}).get("version")
        },

        "bitcoin": {
            "network":
                wallet.get("wallet",{}).get("network"),
            "synchronized":
                wallet.get("wallet",{}).get("synchronized"),
            "type":
                wallet.get("wallet",{}).get("type")
        },

        "mining": {
            "mode":
                mining.get("mode"),
            "hashrate":
                mining.get("miner",{}).get("hashrate_display"),
            "warnings":
                mining.get("warnings",[])
        }
    }


    OUTPUT_JSON.write_text(
        json.dumps(summary, indent=2) + "\n"
    )


    rows=[]

    for item in checks:
        rows.append(
            f"""
            <tr>
            <td>{item.get('name')}</td>
            <td>{item.get('state')}</td>
            <td>{item.get('detail')}</td>
            <td>{item.get('recommendation','')}</td>
            </tr>
            """
        )


    OUTPUT_HTML.write_text(
f"""
<!doctype html>
<html>
<head>
<title>WW.CX Edge1 Daily Operations Summary</title>
<style>
body {{
font-family:system-ui;
background:#0b1015;
color:#eee;
padding:30px
}}
table {{
width:100%;
border-collapse:collapse
}}
td,th {{
border:1px solid #444;
padding:10px
}}
</style>
</head>

<body>

<h1>WW.CX Edge1 Daily Operations Summary</h1>

<h2>Overall: {summary['overall']}</h2>

<table>
<tr>
<th>Component</th>
<th>Status</th>
<th>Details</th>
<th>Recommendation</th>
</tr>

{''.join(rows)}

</table>

</body>
</html>
"""
    )

    print("Daily summary generated")


if __name__ == "__main__":
    main()
