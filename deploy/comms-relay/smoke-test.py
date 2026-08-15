#!/usr/bin/env python3
"""Local post-start smoke test for Edge1 Communications Relay."""
from __future__ import annotations

import argparse
import json
import socket
import time
import urllib.request
from pathlib import Path


def irc_probe(host: str, port: int) -> None:
    with socket.create_connection((host, port), timeout=3) as sock:
        sock.settimeout(3)
        sock.sendall(b"PING :edge1-smoke\r\n")
        data = sock.recv(1024)
    if b" PONG " not in data:
        raise RuntimeError(f"unexpected IRC probe response on {host}:{port}: {data!r}")


def nntp_probe(host: str, port: int) -> None:
    with socket.create_connection((host, port), timeout=3) as sock:
        sock.settimeout(3)
        data = sock.recv(1024)
    if not data.startswith(b"200 "):
        raise RuntimeError(f"unexpected NNTP greeting on {host}:{port}: {data!r}")


def control_probe(host: str, port: int) -> None:
    url = f"http://{host}:{port}/healthz"
    with urllib.request.urlopen(url, timeout=3) as response:
        payload = json.loads(response.read())
    if payload.get("status") != "ok":
        raise RuntimeError(f"control health failed: {payload!r}")


def probe_once(config_path: Path) -> None:
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    listeners = cfg["listeners"]
    if listeners["irc"]["enabled"]:
        irc_probe(listeners["irc"]["host"], int(listeners["irc"]["port"]))
    if listeners["nntp"]["enabled"]:
        nntp_probe(listeners["nntp"]["host"], int(listeners["nntp"]["port"]))
    if listeners["control"]["enabled"]:
        control_probe(listeners["control"]["host"], int(listeners["control"]["port"]))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="/etc/wwcx/comms-relay.json")
    parser.add_argument("--attempts", type=int, default=12)
    parser.add_argument("--delay", type=float, default=0.5)
    args = parser.parse_args()
    if args.attempts < 1:
        parser.error("--attempts must be positive")
    if args.delay < 0:
        parser.error("--delay must be non-negative")

    last_error: Exception | None = None
    for attempt in range(1, args.attempts + 1):
        try:
            probe_once(Path(args.config))
            print(f"PASS Edge1 Communications Relay smoke test (attempt {attempt}/{args.attempts})")
            return 0
        except (OSError, RuntimeError, ValueError, KeyError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt < args.attempts:
                time.sleep(args.delay)

    raise SystemExit(f"FAIL Edge1 Communications Relay smoke test after {args.attempts} attempts: {last_error}")


if __name__ == "__main__":
    raise SystemExit(main())
