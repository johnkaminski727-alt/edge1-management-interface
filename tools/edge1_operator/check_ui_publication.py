#!/usr/bin/env python3
"""Protect UI publication from uncommitted source, live drift, and old revisions."""
import argparse, hashlib, json, os, subprocess
from pathlib import Path
ROOT = Path("/opt/edge1-management-interface")
STATE = Path("/var/lib/edge1-ui-publication/baseline.json")
def git(*args):
    return subprocess.check_output(["git", "-c", f"safe.directory={ROOT}", *args], cwd=ROOT, text=True).strip()
def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["check", "record"])
    args = parser.parse_args()
    if not STATE.is_file():
        raise SystemExit("STOP: publication baseline is missing; reconcile live files first.")
    data = json.loads(STATE.read_text())
    if args.mode == "check":
        if git("status", "--porcelain"):
            raise SystemExit("STOP: commit and review repository changes before publishing.")
        ancestor = subprocess.run(["git", "-c", f"safe.directory={ROOT}", "merge-base", "--is-ancestor", data["head"], "HEAD"], cwd=ROOT)
        if ancestor.returncode:
            raise SystemExit("STOP: this revision does not include the last published checkpoint.")
    errors = []
    for item in data["files"]:
        current = digest(Path(item["live"]))
        if current != item["sha256"]:
            if args.mode == "record" and current == digest(ROOT / item["source"]):
                item["sha256"] = current
            else:
                errors.append(item["live"])
    if errors:
        raise SystemExit("STOP: unreviewed live drift:\n" + "\n".join(errors))
    if args.mode == "record":
        data["head"] = git("rev-parse", "HEAD")
        tmp = STATE.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2) + "\n")
        os.chmod(tmp, 0o600)
        os.replace(tmp, STATE)
    print("PASS: UI publication " + args.mode)
if __name__ == "__main__":
    main()
