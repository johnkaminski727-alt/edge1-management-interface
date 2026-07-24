#!/usr/bin/env python3

from pathlib import Path
import json
import datetime

OUTPUT = Path("/var/www/edge1-status/operations-health.json")


def load(path):
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def main():

    security = load(
        Path("/var/www/edge1-status/security-operations.json")
    )

    wallet = load(
        Path("/var/www/edge1-status/bitcoin-wallet.json")
    )

    mining = load(
        Path("/var/www/edge1-status/bitcoin-mining.json")
    )

    checks=[]

    sec_ok = security.get("health",{}).get("status") == "healthy"

    checks.append({
        "name":"Security",
        "state":"healthy" if sec_ok else "warning",
        "detail":
            "Suricata operational"
            if sec_ok
            else "; ".join(
                security.get("health",{}).get("warnings",[])
            )
    })


    btc_ok = (
        wallet.get("wallet",{}).get("synchronized")
        and wallet.get("service",{}).get("connected")
    )

    checks.append({
        "name":"Bitcoin",
        "state":"healthy" if btc_ok else "warning",
        "detail":
            "Watch-only wallet synchronized"
            if btc_ok
            else "Wallet telemetry requires attention"
    })


    mining_warning = mining.get("warnings",[])

    checks.append({
        "name":"Mining",
        "state":"warning" if mining_warning else "healthy",
        "detail":
            "; ".join(mining_warning)
            if mining_warning
            else "Mining telemetry healthy"
    })


    overall = (
        "healthy"
        if all(x["state"]=="healthy" for x in checks)
        else "attention"
    )


    OUTPUT.write_text(
        json.dumps(
            {
                "generated_at":
                    datetime.datetime.now(
                        datetime.timezone.utc
                    ).isoformat(),
                "overall": overall,
                "checks": checks
            },
            indent=2
        )+"\n"
    )


if __name__=="__main__":
    main()
