#!/usr/bin/env python3

from pathlib import Path
import subprocess
import json
import datetime

OUTPUT = Path("/var/www/edge1-status/operations-changes.json")

ROOT = Path("/opt/edge1-management-interface")


def run(args):
    return subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False
    ).stdout.strip()


def main():

    branch = run([
        "git",
        "branch",
        "--show-current"
    ])

    status = run([
        "git",
        "status",
        "--porcelain"
    ])

    commits_raw = run([
        "git",
        "log",
        "-5",
        "--pretty=format:%h|%s"
    ])

    commits=[]

    for line in commits_raw.splitlines():
        if "|" in line:
            h,msg=line.split("|",1)
            commits.append({
                "hash":h,
                "message":msg
            })

    data={
        "generated_at":
            datetime.datetime.now(
                datetime.timezone.utc
            ).isoformat(),

        "branch":branch,

        "clean":
            status == "",

        "head":
            commits[0]["hash"]
            if commits else "",

        "recent_commits":
            commits
    }

    OUTPUT.write_text(
        json.dumps(data,indent=2)+"\n"
    )


if __name__=="__main__":
    main()
