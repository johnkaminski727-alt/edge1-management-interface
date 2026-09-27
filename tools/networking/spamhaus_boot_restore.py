#!/usr/bin/env python3
"""Conservative Spamhaus boot restore helper.

Default mode is check-only. Explicit --execute may apply one already-validated
candidate only when the dedicated table is absent. It never flushes the ruleset,
never touches UFW/CrowdSec tables and never refreshes feeds.
"""
from __future__ import annotations
import argparse, json, subprocess
from pathlib import Path

NFT="/usr/sbin/nft"
TARGET=("inet","bigbird_spamhaus")

def run(args):
    return subprocess.run(args,capture_output=True,text=True,check=False,timeout=30)

def table_present():
    r=run([NFT,"-j","list","tables"])
    if r.returncode:
        raise RuntimeError("cannot inspect nftables tables")
    try:
        data=json.loads(r.stdout)
        tables={(e["table"]["family"],e["table"]["name"]) for e in data["nftables"] if "table" in e}
    except Exception as exc:
        raise RuntimeError("cannot parse nftables table listing") from exc
    return TARGET in tables

def restore(candidate:Path, *, execute=False):
    if not candidate.is_file() or candidate.is_symlink():
        raise RuntimeError("candidate missing or unsafe")
    if table_present():
        return "already_present"
    chk=run([NFT,"--check","--file",str(candidate)])
    if chk.returncode:
        raise RuntimeError("candidate failed nftables check")
    if not execute:
        return "eligible_check_only"
    apply=run([NFT,"--file",str(candidate)])
    if apply.returncode:
        raise RuntimeError("candidate apply failed")
    if not table_present():
        raise RuntimeError("Spamhaus table absent after apply")
    return "restored_verified"

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--candidate",type=Path,required=True)
    g=p.add_mutually_exclusive_group()
    g.add_argument("--check-only",action="store_true")
    g.add_argument("--execute",action="store_true")
    a=p.parse_args()
    try:
        state=restore(a.candidate,execute=a.execute)
    except (RuntimeError,OSError,subprocess.SubprocessError) as exc:
        p.exit(1,"STOP: "+str(exc)+"\n")
    print("Spamhaus boot restore:",state)

if __name__=="__main__":
    main()
