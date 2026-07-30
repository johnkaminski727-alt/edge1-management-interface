#!/usr/bin/env python3
"""Apply schedule-aware freshness limits to the final read-only Network Defense exporter."""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
from pathlib import Path

FINAL_PATH = Path(__file__).with_name('network_defense_nftables_exporter.py')
SPEC = importlib.util.spec_from_file_location('network_defense_final', FINAL_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f'Unable to load final Network Defense exporter: {FINAL_PATH}')
FINAL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FINAL)

# operations-network.json is produced every 300 seconds. Network Defense runs every
# 60 seconds with up to 10 seconds of randomized delay, so a five-minute limit can
# mark a healthy source stale between normal producer runs. Ten minutes matches the
# established live-acceptance ceiling while still detecting two missed producer runs.
NETWORK_STALE_SECONDS = 10 * 60
FINAL.BASE.BASE.BASE.SOURCE_STALE_SECONDS['network'] = NETWORK_STALE_SECONDS


def build_snapshot(
    network_path: Path = FINAL.BASE.BASE.BASE.DEFAULT_NETWORK,
    security_path: Path = FINAL.BASE.BASE.BASE.DEFAULT_SECURITY,
    correlation_path: Path = FINAL.BASE.BASE.BASE.DEFAULT_CORRELATION,
    operations_path: Path = FINAL.BASE.BASE.BASE.DEFAULT_OPERATIONS,
    spamhaus_path: Path = FINAL.BASE.BASE.BASE.DEFAULT_SPAMHAUS,
    spamhaus_live_state_path: Path = FINAL.BASE.BASE.BASE.DEFAULT_SPAMHAUS_LIVE_STATE,
    dns_policy_path: Path = FINAL.BASE.BASE.DEFAULT_DNS_POLICY,
    fail2ban_live_state_path: Path = FINAL.BASE.DEFAULT_FAIL2BAN_LIVE_STATE,
    nftables_live_state_path: Path = FINAL.DEFAULT_NFTABLES_LIVE_STATE,
    now: dt.datetime | None = None,
):
    return FINAL.build_snapshot(
        network_path=network_path,
        security_path=security_path,
        correlation_path=correlation_path,
        operations_path=operations_path,
        spamhaus_path=spamhaus_path,
        spamhaus_live_state_path=spamhaus_live_state_path,
        dns_policy_path=dns_policy_path,
        fail2ban_live_state_path=fail2ban_live_state_path,
        nftables_live_state_path=nftables_live_state_path,
        now=now,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--network', type=Path, default=FINAL.BASE.BASE.BASE.DEFAULT_NETWORK)
    parser.add_argument('--security', type=Path, default=FINAL.BASE.BASE.BASE.DEFAULT_SECURITY)
    parser.add_argument('--correlation', type=Path, default=FINAL.BASE.BASE.BASE.DEFAULT_CORRELATION)
    parser.add_argument('--operations', type=Path, default=FINAL.BASE.BASE.BASE.DEFAULT_OPERATIONS)
    parser.add_argument('--spamhaus', type=Path, default=FINAL.BASE.BASE.BASE.DEFAULT_SPAMHAUS)
    parser.add_argument('--spamhaus-live-state', type=Path, default=FINAL.BASE.BASE.BASE.DEFAULT_SPAMHAUS_LIVE_STATE)
    parser.add_argument('--dns-policy', type=Path, default=FINAL.BASE.BASE.DEFAULT_DNS_POLICY)
    parser.add_argument('--fail2ban-live-state', type=Path, default=FINAL.BASE.DEFAULT_FAIL2BAN_LIVE_STATE)
    parser.add_argument('--nftables-live-state', type=Path, default=FINAL.DEFAULT_NFTABLES_LIVE_STATE)
    parser.add_argument('--output', type=Path, default=FINAL.BASE.BASE.BASE.DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    snapshot = build_snapshot(
        network_path=args.network,
        security_path=args.security,
        correlation_path=args.correlation,
        operations_path=args.operations,
        spamhaus_path=args.spamhaus,
        spamhaus_live_state_path=args.spamhaus_live_state,
        dns_policy_path=args.dns_policy,
        fail2ban_live_state_path=args.fail2ban_live_state,
        nftables_live_state_path=args.nftables_live_state,
    )
    FINAL.BASE.BASE.BASE.write_snapshot(snapshot, args.output)
    print(json.dumps({
        'ok': True,
        'output': str(args.output),
        'overall_state': snapshot['overall_state'],
        'network_stale_after_seconds': snapshot['sources']['network']['stale_after_seconds'],
        'verified_enforcement_count': snapshot['summary']['verified_enforcement_count'],
        'traffic_controls_changed': False,
    }))


if __name__ == '__main__':
    main()
