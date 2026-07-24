#!/usr/bin/env python3

from pathlib import Path
import subprocess
import json
import datetime
import platform

OUTPUT = Path("/var/www/edge1-status/operations-inventory.json")


def run(args):
    return subprocess.run(
        args,
        text=True,
        capture_output=True,
        check=False
    ).stdout.strip()


def main():

    services = run([
        "systemctl",
        "list-units",
        "--type=service",
        "--state=running",
        "--no-pager",
        "--plain"
    ])

    data = {
        "generated_at":
            datetime.datetime.now(
                datetime.timezone.utc
            ).isoformat(),

        "host": platform.node(),

        "kernel": platform.release(),

        "python": platform.python_version(),

        "modules": [
            "security",
            "bitcoin",
            "mining",
            "telephony",
            "messaging",
            "operations-center"
        ],

        "running_services": [
            line.strip()
            for line in services.splitlines()
            if line.strip()
        ][:100]
    }


    OUTPUT.write_text(
        json.dumps(data, indent=2)+"\n"
    )


if __name__ == "__main__":
    main()
