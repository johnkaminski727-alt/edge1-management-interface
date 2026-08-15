#!/usr/bin/env python3
"""Probe a public NTS-KE endpoint with certificate and ALPN verification."""

import argparse
import datetime as dt
import json
import os
import socket
import ssl
import time
from pathlib import Path
from typing import Any, Dict, Optional

SCHEMA_VERSION = 1


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def write_atomic(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    os.chmod(str(temp), 0o600)
    os.replace(str(temp), str(path))


def probe(
    server_name: str,
    *,
    port: int,
    observer_id: str,
    observer_host: str,
    timeout: float,
) -> Dict[str, Any]:
    record = {  # type: Dict[str, Any]
        "schema_version": SCHEMA_VERSION,
        "observed_at_utc": utc_now(),
        "observer_id": observer_id,
        "observer_host": observer_host,
        "server_name": server_name,
        "port": port,
        "reachable": False,
        "resolved_address": None,
        "tls_verified": False,
        "alpn": None,
        "rtt_ms": None,
        "certificate_not_after_utc": None,
        "error": None,
    }

    raw = None  # type: Optional[socket.socket]
    tls = None  # type: Optional[ssl.SSLSocket]
    try:
        if not getattr(ssl, "HAS_ALPN", False):
            raise RuntimeError("alpn_not_supported")

        address = socket.gethostbyname(server_name)
        record["resolved_address"] = address

        context = ssl.create_default_context()
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED
        context.set_alpn_protocols(["ntske/1"])

        started = time.monotonic()
        raw = socket.create_connection((address, port), timeout=timeout)
        tls = context.wrap_socket(raw, server_hostname=server_name)
        raw = None
        finished = time.monotonic()

        record["tls_verified"] = True
        record["rtt_ms"] = round((finished - started) * 1000.0, 3)
        record["resolved_address"] = tls.getpeername()[0]
        record["alpn"] = tls.selected_alpn_protocol()

        certificate = tls.getpeercert()
        not_after = certificate.get("notAfter") if isinstance(certificate, dict) else None
        if not_after:
            expiry = ssl.cert_time_to_seconds(str(not_after))
            record["certificate_not_after_utc"] = dt.datetime.fromtimestamp(
                expiry, tz=dt.timezone.utc
            ).isoformat(timespec="seconds").replace("+00:00", "Z")

        if record["alpn"] != "ntske/1":
            raise ValueError("unexpected_alpn_{}".format(record["alpn"] or "none"))

        record["reachable"] = True
    except (OSError, ssl.SSLError, ValueError, RuntimeError) as exc:
        record["error"] = exc.__class__.__name__ + ":" + str(exc)[:160]
    finally:
        if tls is not None:
            try:
                tls.close()
            except OSError:
                pass
        if raw is not None:
            try:
                raw.close()
            except OSError:
                pass

    return record


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server-name", default="ntp.ww.cx")
    parser.add_argument("--port", type=int, default=4460)
    parser.add_argument("--observer-id", required=True)
    parser.add_argument("--observer-host", default=socket.getfqdn())
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not 1 <= args.port <= 65535:
        raise SystemExit("--port must be between 1 and 65535")
    if not 0.25 <= args.timeout <= 30:
        raise SystemExit("--timeout must be between 0.25 and 30 seconds")

    record = probe(
        args.server_name,
        port=args.port,
        observer_id=args.observer_id,
        observer_host=args.observer_host,
        timeout=args.timeout,
    )
    if args.output:
        write_atomic(args.output, record)
    if args.pretty:
        print(json.dumps(record, indent=2, sort_keys=True))
    else:
        print(json.dumps(record, sort_keys=True, separators=(",", ":")))
    return 0 if record["reachable"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
