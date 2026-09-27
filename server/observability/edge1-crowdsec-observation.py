#!/usr/bin/python3
import datetime
import json
import os
from pathlib import Path
import subprocess
import tempfile

OUTPUT = Path("/var/www/edge1-status/crowdsec-status.json")

def run(*args):
    try:
        result = subprocess.run(
            args, capture_output=True, text=True,
            timeout=20, check=False
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None

def service(name):
    active = run("systemctl", "is-active", name)
    enabled = run("systemctl", "is-enabled", name)
    return {
        "active": active == "active",
        "enabled": enabled == "enabled",
        "observed": active is not None,
    }

def nft_objects(kind, family, table, name):
    raw = run("nft", "-j", "list", kind, family, table, name)
    if raw is None:
        return None
    try:
        return json.loads(raw)["nftables"]
    except (ValueError, KeyError, TypeError):
        return None

def chain(family, table, name, hook):
    objects = nft_objects("chain", family, table, name)
    if objects is None:
        return {"verified": False, "state": "unavailable"}

    chains = [x["chain"] for x in objects if "chain" in x]
    verified = (
        len(chains) == 1
        and chains[0].get("hook") == hook
        and chains[0].get("prio") == -10
    )
    answer = {
        "verified": verified,
        "state": "observed" if verified else "unexpected",
    }

    if hook == "forward":
        rules = [x["rule"] for x in objects if "rule" in x]
        packets = []
        directions = [
            ("wg0", "ens3", "daddr"),
            ("ens3", "wg0", "saddr"),
        ]
        valid = verified and len(rules) == 2

        for index, direction in enumerate(directions):
            if index >= len(rules):
                valid = False
                packets.append(None)
                continue

            rule = rules[index]
            expressions = rule.get("expr", [])
            encoded = json.dumps(expressions)
            counters = [
                x["counter"] for x in expressions
                if "counter" in x
            ]
            correct = all(token in encoded for token in (
                direction[0],
                direction[1],
                direction[2],
                "crowdsec-blacklists",
                "drop",
            ))
            valid = valid and correct and len(counters) == 1
            packets.append(
                counters[0].get("packets")
                if len(counters) == 1 else None
            )

        answer["verified"] = valid
        answer["state"] = "observed" if valid else "unexpected"
        answer["rule_count"] = len(rules)
        answer["drop_packets"] = packets

    return answer

def blacklist(family, table, name):
    objects = nft_objects("set", family, table, name)
    if objects is None:
        return {"available": False, "count": None}

    sets = [x["set"] for x in objects if "set" in x]
    if len(sets) != 1:
        return {"available": False, "count": None}

    elements = sets[0].get("elem", [])
    return {
        "available": isinstance(elements, list),
        "count": len(elements) if isinstance(elements, list)
                 else None,
    }

def main():
    services = {
        name: service(name)
        for name in (
            "ufw", "wg-quick@wg0", "wireguard-nat",
            "crowdsec", "crowdsec-firewall-bouncer",
            "edge1-crowdsec-bootstrap",
            "edge1-crowdsec-enforce",
            "edge1-crowdsec-forward",
            "AdGuardHome", "unbound",
        )
    }

    snapshot = {
        "schema_version": "wwcx.crowdsec-observation.v1",
        "generated_at": datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat(),
        "read_only": True,
        "traffic_controls_changed": False,
        "input": {
            "ipv4": chain(
                "ip", "crowdsec", "edge1-enforce-input", "input"
            ),
            "ipv6": chain(
                "ip6", "crowdsec6", "edge1-enforce-input", "input"
            ),
        },
        "forward": {
            "ipv4": chain(
                "ip", "crowdsec",
                "edge1-enforce-forward", "forward"
            ),
            "ipv6": {
                "verified": False,
                "state": "not_deployed",
            },
        },
        "blacklists": {
            "ipv4": blacklist(
                "ip", "crowdsec", "crowdsec-blacklists"
            ),
            "ipv6": blacklist(
                "ip6", "crowdsec6", "crowdsec6-blacklists"
            ),
        },
        "services": services,
        "limitations": [
            "Snapshot freshness is not threat-feed freshness",
            "Counters are cumulative since rule creation",
            "Current hook state alone does not prove all traffic paths",
            "IPv6 VPN forwarding is not deployed",
        ],
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=".crowdsec-", suffix=".tmp",
        dir=str(OUTPUT.parent)
    )
    try:
        with os.fdopen(descriptor, "w") as handle:
            json.dump(snapshot, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o644)
        os.replace(temporary, OUTPUT)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

    print("IPv4 INPUT:", snapshot["input"]["ipv4"]["state"])
    print("IPv6 INPUT:", snapshot["input"]["ipv6"]["state"])
    print("IPv4 FORWARD:", snapshot["forward"]["ipv4"]["state"])
    print("IPv4 blacklist:",
          snapshot["blacklists"]["ipv4"]["count"])
    print("IPv6 blacklist:",
          snapshot["blacklists"]["ipv6"]["count"])

if __name__ == "__main__":
    main()
