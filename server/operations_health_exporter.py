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

    memory_bytes = int(
        security.get("engine",{}).get("MemoryCurrent",0) or 0
    )

    memory_gb = round(memory_bytes / (1024**3), 2)

    security_warning = (
        memory_bytes > 1250000000
        or not sec_ok
    )

    checks.append({
        "name":"Security",
        "state":"warning" if security_warning else "healthy",
        "reason_code":
            "security.memory.elevated"
            if memory_bytes > 1250000000
            else "",
        "detail":
            f"Suricata memory {memory_gb} GB"
            if security_warning
            else "Suricata operational",
        "recommendation":
            "Monitor Suricata resource usage and event load."
            if memory_bytes > 1250000000
            else "No action required."
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
        "reason_code":
            "mining.hardware.not_configured"
            if mining_warning
            else "",
        "detail":
            "; ".join(mining_warning)
            if mining_warning
            else "Mining telemetry healthy",
        "recommendation":
            "Configure mining hardware if production mining is intended."
            if mining_warning
            else "No action required."
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
