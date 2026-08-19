from __future__ import annotations

import argparse
import json
import os

from .delivery_status import PostgresDeliveryStatusStore


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconcile one WW.CX delivery status with a known outbound message")
    parser.add_argument("--once", action="store_true", help="required safety gate; reconcile at most one state")
    args = parser.parse_args()

    if not args.once:
        parser.error("--once is required; continuous delivery reconciliation is not enabled")

    if os.getenv("WWCX_DELIVERY_RECONCILE_ENABLED", "false").lower() != "true":
        print(json.dumps({"status": "disabled"}))
        return 2

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print(json.dumps({"status": "error", "reason": "DATABASE_URL is required"}))
        return 2

    result = PostgresDeliveryStatusStore(database_url).reconcile_one()
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
