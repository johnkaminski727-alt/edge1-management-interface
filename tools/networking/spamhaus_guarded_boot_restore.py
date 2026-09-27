#!/usr/bin/env python3
"""Assignment 240: staged guarded Spamhaus boot restoration.

Default: check-only. --execute arms an independent, scoped systemd rollback
BEFORE applying the protected pinned candidate. Never cancels rollback itself.
No feed download, no global nft flush, no changes to other firewall tables.
"""
from __future__ import annotations
import argparse
import json
import os
import subprocess
from pathlib import Path

NFT = "/usr/sbin/nft"
PYTHON = "/usr/bin/python3"
SYSTEMCTL = "/usr/bin/systemctl"
SYSTEMD_RUN = "/usr/bin/systemd-run"
CHRONYC = "/usr/bin/chronyc"
STAGE = Path("/var/lib/edge1-spamhaus/boot-candidate")
LIBEXEC = Path("/usr/local/libexec/edge1-spamhaus")
RECOVERY = LIBEXEC / "spamhaus_scoped_recovery.py"
PARSER = LIBEXEC / "spamhaus_feed_candidate.py"
PREFLIGHT = LIBEXEC / "spamhaus_boot_preflight.py"
CANDIDATE = STAGE / "spamhaus-candidate.nft"
TIMER = "edge1-spamhaus-rollback.timer"
SERVICE = "edge1-spamhaus-rollback.service"
REQUIRED_SERVICES = ("ssh.service", "ufw.service", "crowdsec.service", "crowdsec-firewall-bouncer.service")
TARGET = ("inet", "bigbird_spamhaus")


def run(command, *, timeout=60):
    return subprocess.run(command, capture_output=True, text=True, check=False, timeout=timeout)


def require(command, message, *, timeout=60):
    outcome = run(command, timeout=timeout)
    if outcome.returncode:
        raise RuntimeError(message)
    return outcome.stdout


def table_present():
    raw = require([NFT, "-j", "list", "tables"], "Cannot inspect firewall tables")
    try:
        doc = json.loads(raw)
        return TARGET in {
            (entry["table"]["family"], entry["table"]["name"])
            for entry in doc["nftables"] if "table" in entry
        }
    except (TypeError, ValueError, KeyError) as exc:
        raise RuntimeError("Cannot parse firewall table listing") from exc


def verify_restored_table():
    """Verify deployed policy structure, not merely the table name."""
    raw = require([NFT, "-j", "list", "table", *TARGET], "Cannot inspect restored Spamhaus table")
    try:
        entries = json.loads(raw)["nftables"]
        sets = {e["set"]["name"]: e["set"] for e in entries if "set" in e}
        chains = {e["chain"]["name"]: e["chain"] for e in entries if "chain" in e}
        rules = [e["rule"] for e in entries if "rule" in e]
        if set(sets) != {"drop4", "drop6"}:
            raise ValueError("Unexpected sets")
        if sets["drop4"]["type"] != "ipv4_addr" or sets["drop6"]["type"] != "ipv6_addr":
            raise ValueError("Unexpected set types")
        if any(not s.get("elem") or "interval" not in s.get("flags", []) for s in sets.values()):
            raise ValueError("Empty blocked-address set")
        for name in ("input", "forward"):
            chain = chains[name]
            if chain.get("hook") != name or chain.get("prio") != -110 or chain.get("policy") != "accept" or chain.get("type") != "filter":
                raise ValueError("Unexpected hook/priority/policy")
            matching = [r for r in rules if r.get("chain") == name]
            if len(matching) != 2:
                raise ValueError("Missing or additional DROP rules")
            for expected_family, expected_set in (("ip", "drop4"), ("ip6", "drop6")):
                family_rules = [r for r in matching if
                    any(isinstance(x, dict) and "match" in x and
                        x["match"].get("left", {}).get("payload", {}).get("protocol") == expected_family and
                        x["match"].get("right") == "@" + expected_set
                        for x in r.get("expr", []))]
                if len(family_rules) != 1 or not any(
                    isinstance(x, dict) and "drop" in x for x in family_rules[0].get("expr", [])
                ):
                    raise ValueError("Missing correct source-set DROP rule")
    except (TypeError, ValueError, KeyError, IndexError) as exc:
        raise RuntimeError("Restored table structure verification failed") from exc


def validate_sources():
    if STAGE.is_symlink() or not STAGE.is_dir():
        raise RuntimeError("Pinned candidate directory missing or unsafe")
    if os.geteuid() == 0 and (STAGE.stat().st_uid != 0 or STAGE.stat().st_mode & 0o077):
        raise RuntimeError("Pinned candidate directory is not root-owned/private")
    for path in (PARSER, PREFLIGHT, RECOVERY, CANDIDATE):
        if not path.is_file() or path.is_symlink():
            raise RuntimeError("Missing or unsafe required source: " + path.name)
        if os.geteuid() == 0 and (path.stat().st_uid != 0 or path.stat().st_mode & 0o022):
            raise RuntimeError("Required source is not root-owned or is writable by others: " + path.name)
    require([CHRONYC, "waitsync", "30", "0.1"], "Clock is not synchronized", timeout=130)
    for unit in REQUIRED_SERVICES:
        require([SYSTEMCTL, "is-active", "--quiet", unit], "Required service not active: " + unit)
    require([PYTHON, "-B", str(PREFLIGHT), "--stage", str(STAGE),
             "--parser", str(PARSER), "--recovery", str(RECOVERY)],
            "Candidate integrity/freshness preflight failed")
    require([NFT, "--check", "--file", str(CANDIDATE)], "Candidate nft check failed")


def arm_rollback():
    # The fixed transient unit name intentionally fails closed if already occupied.
    # No shell expansion, global firewall snapshot, or repository-local recovery.
    require([SYSTEMD_RUN, "--unit=edge1-spamhaus-rollback",
             "--on-active=180s", "--timer-property=AccuracySec=1s",
             PYTHON, "-B", str(RECOVERY), "--execute"],
            "Independent rollback timer could not be armed")
    state = require([SYSTEMCTL, "show", TIMER, "--property=ActiveState", "--value"],
                    "Cannot verify rollback timer state").strip()
    if state != "active":
        raise RuntimeError("Rollback timer not active")
    props = require([SYSTEMCTL, "show", SERVICE, "--property=ExecStart", "--value"],
                    "Cannot inspect independent rollback command")
    if not (("path=" + PYTHON + " ;") in props and
            ("argv[]=" + PYTHON + " -B " + str(RECOVERY) + " --execute ;") in props):
        raise RuntimeError("Rollback command is not the independently installed scoped recovery")


def guarded_restore(*, execute=False):
    # An existing table is never replaced; do not arm a timer that would remove it.
    if table_present():
        return "already_present"
    validate_sources()
    if not execute:
        return "eligible_check_only"
    arm_rollback()
    # If this or later checks fail, intentionally leave the rollback timer armed.
    if table_present():
        raise RuntimeError("Table appeared after rollback arming: manual inspection required; timer remains armed")
    require([NFT, "--file", str(CANDIDATE)], "Candidate application failed; rollback remains armed")
    verify_restored_table()
    for unit in REQUIRED_SERVICES:
        require([SYSTEMCTL, "is-active", "--quiet", unit],
                "Service failed after apply; rollback remains armed: " + unit)
    return "restored_verified_rollback_armed"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    try:
        state = guarded_restore(execute=args.execute)
    except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
        parser.exit(1, "STOP: " + str(exc) + "\n")
    print("Guarded restore:", state)


if __name__ == "__main__":
    main()
