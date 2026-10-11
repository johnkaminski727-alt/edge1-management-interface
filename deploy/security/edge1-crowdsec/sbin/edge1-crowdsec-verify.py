#!/usr/bin/env python3
"""Shared verifier for the isolated Edge1 CrowdSec nftables tables.

Usage: edge1-crowdsec-verify.py bootstrap|enforce-pre|enforce-post
Accepts both a fresh bootstrap (guard chain only) and an already-enforced
state (guard + edge1-enforce-input [+ edge1-enforce-forward]), so restarting
the units is idempotent. Anything else fails. Never prints set elements.
"""
import json, subprocess, sys

MODE = sys.argv[1] if len(sys.argv) > 1 else "bootstrap"
ALLOWED_EXTRA = {"edge1-enforce-input": "input", "edge1-enforce-forward": "forward"}
TABLES = (("ip", "crowdsec", "crowdsec-blacklists"), ("ip6", "crowdsec6", "crowdsec6-blacklists"))

def check(family, table, blacklist):
    data = json.loads(subprocess.check_output(["nft", "-j", "list", "table", family, table], text=True))["nftables"]
    chains = {c["name"]: c for c in (x["chain"] for x in data if "chain" in x)}
    rules = [x["rule"] for x in data if "rule" in x]
    sets = [x["set"] for x in data if "set" in x and x["set"]["name"] == blacklist]

    assert "edge1-guard" in chains, "guard chain missing"
    assert "hook" not in chains["edge1-guard"], "guard chain must not be hooked"
    assert len([r for r in rules if r["chain"] == "edge1-guard"]) == 3, "guard chain must have exactly 3 rules"
    assert len(sets) == 1 and "timeout" in sets[0].get("flags", []), "blacklist set missing or without timeout"

    extra = {n: c for n, c in chains.items() if n != "edge1-guard"}
    for name, chain in extra.items():
        assert name in ALLOWED_EXTRA, f"unexpected chain {name}"
        assert chain.get("hook") == ALLOWED_EXTRA[name], f"{name} has wrong hook"
        assert chain.get("prio") == -10, f"{name} has wrong priority"
    hook = extra.get("edge1-enforce-input")
    if hook is not None:
        hook_rules = [r for r in rules if r["chain"] == "edge1-enforce-input"]
        assert len(hook_rules) == 1 and any("jump" in e and e["jump"].get("target") == "edge1-guard" for e in hook_rules[0]["expr"]), \
            "edge1-enforce-input must contain only 'jump edge1-guard'"
    if MODE == "enforce-post":
        assert hook is not None, "enforcement hook not installed"
    return hook is not None

installed = [check(*t) for t in TABLES]
if MODE == "enforce-pre":
    assert installed[0] == installed[1], "partial enforcement state (only one family hooked)"
    print("ALREADY_INSTALLED" if all(installed) else "NOT_INSTALLED")
else:
    for (family, _, _), hooked in zip(TABLES, installed):
        print(f"PASS: {family} guard and set verified" + (" (enforcement hook present)" if hooked else ""))
