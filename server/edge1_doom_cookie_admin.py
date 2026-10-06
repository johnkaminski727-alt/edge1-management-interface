#!/usr/bin/env python3
"""Local operator review and release; no HTTP administrative endpoint."""
import argparse, json
from pathlib import Path
from server.edge1_doom_cookie import DoomStore
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("action",choices=["list","verify","release"])
    parser.add_argument("--subject")
    parser.add_argument("--actor")
    parser.add_argument("--reason")
    args=parser.parse_args()
    state=Path("/var/lib/wwcx-edge1-ops/doom-cookie")
    store=DoomStore(state/"evidence.sqlite",(state/"signing.key").read_bytes())
    if args.action=="verify":
        valid=store.verify(); print("PASS" if valid else "FAIL"); return 0 if valid else 1
    if args.action=="release":
        store.release(args.subject,args.actor,args.reason)
        print("Released; escalation history preserved."); return 0
    with store.connect() as db:
        rows=[dict(zip(["subject","tier","strikes","blocked_until"],r)) for r in
            db.execute("SELECT id,tier,strikes,blocked_until FROM subjects ORDER BY blocked_until DESC")]
    print(json.dumps(rows,indent=2)); return 0
if __name__=="__main__": raise SystemExit(main())
