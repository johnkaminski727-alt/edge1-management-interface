#!/usr/bin/env python3
"""Operator CLI for Edge1 SNMP inventory, MIBs, discovery, alerts and search."""
from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import subprocess

from edge1_snmp_platform import connect_db, list_devices
from edge1_snmp_secure_exec import SecureNetSNMP
from edge1_snmp_services import AlertEngine, DiscoveryService, MIBService, ensure_extended_schema, get_topology, search_all


def out(value):
    print(json.dumps(value, sort_keys=True, indent=2, default=str))


def main():
    parser = argparse.ArgumentParser(prog="edge1-snmp")
    sub = parser.add_subparsers(dest="cmd", required=True)
    oid = sub.add_parser("oid")
    oid_sub = oid.add_subparsers(dest="oid_cmd", required=True)
    for name in ("lookup", "describe", "search"):
        query = oid_sub.add_parser(name)
        query.add_argument("value")
    mib = sub.add_parser("mib")
    mib_sub = mib.add_subparsers(dest="mib_cmd", required=True)
    mib_sub.add_parser("list")
    import_parser = mib_sub.add_parser("import")
    import_parser.add_argument("module")
    validate = mib_sub.add_parser("validate")
    validate.add_argument("module")
    discovery = sub.add_parser("discovery")
    discovery.add_argument("cidr")
    discovery.add_argument("--credential-reference", required=True)
    discovery.add_argument("--execute", action="store_true")
    discovery.add_argument("--concurrency", type=int, default=16)
    sub.add_parser("devices")
    sub.add_parser("alerts-evaluate")
    sub.add_parser("topology")
    search = sub.add_parser("search")
    search.add_argument("query")
    args = parser.parse_args()

    conn = connect_db()
    ensure_extended_schema(conn)
    try:
        if args.cmd == "oid":
            service = MIBService(conn)
            result = (service.lookup(args.value) or {"found": False, "query": args.value}) if args.oid_cmd in ("lookup", "describe") else {"results": service.search(args.value)}
            out(result)
        elif args.cmd == "mib":
            service = MIBService(conn)
            if args.mib_cmd == "list":
                out({"imports": [dict(row) for row in conn.execute("SELECT * FROM mib_imports ORDER BY imported_at DESC")]})
            elif args.mib_cmd == "import":
                out(service.import_net_snmp_module(args.module))
            else:
                executable = shutil.which("snmptranslate")
                if not executable:
                    raise SystemExit("snmptranslate is not installed")
                completed = subprocess.run(
                    [executable, "-m", f"+{args.module}", "-Tp"],
                    capture_output=True,
                    text=True,
                    timeout=120,
                    check=False,
                    env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin"},
                )
                out({"module": args.module, "valid": completed.returncode == 0, "detail": (completed.stderr or completed.stdout)[-4000:]})
                return 0 if completed.returncode == 0 else 2
        elif args.cmd == "discovery":
            service = DiscoveryService(net=SecureNetSNMP())
            out(asyncio.run(service.scan(
                args.cidr,
                args.credential_reference,
                dry_run=not args.execute,
                concurrency=args.concurrency,
            )))
        elif args.cmd == "devices":
            out({"devices": list_devices(conn)})
        elif args.cmd == "alerts-evaluate":
            out(AlertEngine(conn).evaluate())
        elif args.cmd == "topology":
            out(get_topology(conn))
        elif args.cmd == "search":
            out(search_all(conn, args.query))
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
