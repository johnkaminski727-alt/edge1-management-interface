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

    telephony = load(
        Path("/var/www/edge1-status/operations-telephony.json")
    )

    messaging = load(
        Path("/var/www/edge1-status/operations-messaging.json")
    )

    inventory = load(
        Path("/var/www/edge1-status/operations-inventory.json")
    )

    checks=[]

    sec_ok = security.get("health",{}).get("status") == "healthy"

    memory_bytes = int(
        security.get("engine",{}).get("MemoryCurrent",0) or 0
    )

    memory_gb = round(memory_bytes / (1024**3), 2)

    if memory_gb >= 2.0:
        security_state = "critical"
        security_reason = "security.memory.critical"
        security_recommendation = "Investigate Suricata memory growth."
    elif memory_gb >= 1.5:
        security_state = "warning"
        security_reason = "security.memory.elevated"
        security_recommendation = "Monitor Suricata resource usage and event load."
    else:
        security_state = "healthy"
        security_reason = ""
        security_recommendation = "No action required."

    if not sec_ok:
        security_state = "warning"
        security_reason = "security.health.warning"
        security_recommendation = "Check Suricata service health."

    elif memory_gb < 1.5:
        security_state = "healthy"
        security_reason = ""
        security_recommendation = "No action required."

    checks.append({
        "name":"Security",
        "state": security_state,
        "reason_code": security_reason,
        "metrics": {
            "memory_gb": memory_gb,
            "warning_threshold_gb": 1.5,
            "critical_threshold_gb": 2.0
        },
        "detail":
            f"Suricata memory {memory_gb} GB",
        "recommendation":
            security_recommendation
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


    telephony_ok = telephony.get("available", False)

    checks.append({
        "name": "Telephony",
        "state": "healthy" if telephony_ok else "warning",
        "reason_code":
            "" if telephony_ok else "telephony.unavailable",
        "detail":
            "Telephony API available"
            if telephony_ok
            else "Telephony API unavailable",
        "recommendation":
            "No action required."
            if telephony_ok
            else "Check telephony service health."
    })


    messaging_ok = (
        messaging.get("available", False)
        and messaging.get("status",{}).get("status") == "ok"
    )

    checks.append({
        "name": "Messaging",
        "state": "healthy" if messaging_ok else "warning",
        "reason_code":
            "" if messaging_ok else "messaging.unavailable",
        "detail":
            "Messaging gateway online"
            if messaging_ok
            else "Messaging gateway unavailable",
        "recommendation":
            "No action required."
            if messaging_ok
            else "Check messaging gateway health."
    })


    inventory_ok = bool(inventory.get("host"))

    checks.append({
        "name": "Inventory",
        "state": "healthy" if inventory_ok else "warning",
        "reason_code":
            "" if inventory_ok else "inventory.unavailable",
        "detail":
            f"Inventory current: {inventory.get('host','unknown')}"
            if inventory_ok
            else "Inventory unavailable",
        "recommendation":
            "No action required."
            if inventory_ok
            else "Check inventory exporter."
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
