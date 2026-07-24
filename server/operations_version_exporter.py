#!/usr/bin/env python3

from pathlib import Path
import subprocess
import json
import datetime

OUTPUT = Path("/var/www/edge1-status/operations-version.json")

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

    data = {
        "generated_at":
            datetime.datetime.now(
                datetime.timezone.utc
            ).isoformat(),

        "branch":
            run(["git","branch","--show-current"]),

        "commit":
            run(["git","rev-parse","--short","HEAD"]),

        "dirty":
            bool(run(["git","status","--short"]))
    }

    OUTPUT.write_text(
        json.dumps(data, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
