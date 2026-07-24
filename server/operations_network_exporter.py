#!/usr/bin/env python3

from pathlib import Path
import subprocess
import json
import datetime

OUTPUT = Path("/var/www/edge1-status/operations-network.json")


def run(args):
    return subprocess.run(
        args,
        text=True,
        capture_output=True,
        check=False
    ).stdout.strip()


def main():

    interfaces = run([
        "ip",
        "-br",
        "addr"
    ])

    routes = run([
        "ip",
        "route"
    ])

    wireguard = run([
        "wg",
        "show"
    ])

    resolver = run([
        "resolvectl",
        "status"
    ])


    data = {
        "generated_at":
            datetime.datetime.now(
                datetime.timezone.utc
            ).isoformat(),

        "interfaces":
            interfaces.splitlines(),

        "routes":
            routes.splitlines()[:50],

        "wireguard_available":
            bool(wireguard),

        "wireguard":
            wireguard[:2000],

        "resolver":
            resolver[:2000]
    }


    OUTPUT.write_text(
        json.dumps(data, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
