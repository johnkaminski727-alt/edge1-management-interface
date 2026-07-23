#!/usr/bin/env python3

from pathlib import Path
from datetime import datetime

BASE = Path(__file__).resolve().parents[2]

def main():
    output = BASE / "reports/operations/capacity-report.md"

    output.write_text(
        f"""# SIP Capacity Report

Generated:
{datetime.utcnow().isoformat()}Z

Current capacity model:

- Carrier inventory tracked
- Peer inventory tracked
- Routing policy tracked
- Failover policy enabled
"""
    )

    print("Capacity report generated")

if __name__ == "__main__":
    main()
