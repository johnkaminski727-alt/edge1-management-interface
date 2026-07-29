#!/usr/bin/env python3
"""Augment Network Defense with sanitized Fail2ban service and jail-health evidence."""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
from pathlib import Path
from typing import Any

BASE_PATH = Path(__file__).with_name('network_defense_dns_exporter.py')
SPEC = importlib.util.spec_from_file_location('network_defense_dns', BASE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f'Unable to load DNS-aware Network Defense exporter: {BASE_PATH}')
BASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BASE)

DEFAULT_FAIL2BAN_LIVE_STATE = Path('/var/lib/bigbird-security/fail2ban/live-state.json')
FAIL2BAN_STALE_SECONDS = 5 * 60
CONTRACT = 'wwcx.fail2ban-live-state.v1'


def load_fail2ban(path: Path) -> tuple[dict[str, Any], str | None]:
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return {}, 'fail2ban live-state source is missing'
    except (OSError, json.JSONDecodeError):
        return {}, 'fail2ban live-state source is unreadable'
    if not isinstance(value, dict):
        return {}, 'fail2ban live-state source is not a JSON object'
    return value, None


def validate_fail2ban(document: dict[str, Any], error: str | None) -> str | None:
    if error:
        return error
    if document.get('contract') != CONTRACT:
        return 'fail2ban live-state contract is unsupported'
    if document.get('read_only') is not True or document.get('traffic_controls_changed') is not False:
        return 'fail2ban live-state safety contract is invalid'
    privacy = document.get('privacy') if isinstance(document.get('privacy'), dict) else {}
    for key in (
        'banned_addresses_included',
        'log_paths_included',
        'raw_client_output_included',
        'commands_included',
        'credentials_included',
        'private_keys_included',
    ):
        if privacy.get(key) is not False:
            return 'fail2ban live-state privacy contract is invalid'
    observation = document.get('observation') if isinstance(document.get('observation'), dict) else {}
    if observation.get('enforcement_verified') is not False:
        return 'fail2ban live-state must not claim enforcement verification'
    if observation.get('state') not in {'active_observed', 'partial', 'inactive', 'not_installed', 'unavailable'}:
        return 'fail2ban live-state observation state is unsupported'
    return None


def source_record(path: Path, error: str | None, now: dt.datetime) -> dict[str, Any]:
    modified: dt.datetime | None = None
    try:
        modified = dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc)
    except OSError:
        pass
    age_seconds = int(max(0, (now - modified).total_seconds())) if modified else None
    return {
        'available': error is None,
        'required': False,
        'file': path.name,
        'modified_at': BASE.BASE.iso(modified),
        'age_seconds': age_seconds,
        'stale_after_seconds': FAIL2BAN_STALE_SECONDS,
        'stale': age_seconds is None or age_seconds > FAIL2BAN_STALE_SECONDS,
        'detail': error or 'loaded',
    }


def append_once(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def augment_snapshot(
    snapshot: dict[str, Any],
    document: dict[str, Any],
    error: str | None,
    path: Path,
    now: dt.datetime,
) -> dict[str, Any]:
    sources = snapshot.setdefault('sources', {})
    components = snapshot.setdefault('components', {})
    recommendations = snapshot.setdefault('recommendations', [])
    warnings = snapshot.setdefault('warnings', [])
    limitations = snapshot.setdefault('limitations', [])

    record = source_record(path, error, now)
    sources['fail2ban_live_state'] = record

    old_recommendation = 'Publish Fail2ban jail health and aggregate ban counts without client-identifying log content.'
    recommendations[:] = [item for item in recommendations if item != old_recommendation]

    if error:
        append_once(warnings, error)
        append_once(recommendations, 'Restore the sanitized Fail2ban live-state source before relying on jail-health status.')
    else:
        observation = document.get('observation') if isinstance(document.get('observation'), dict) else {}
        service = document.get('service') if isinstance(document.get('service'), dict) else {}
        client = document.get('client') if isinstance(document.get('client'), dict) else {}
        jails = document.get('jails') if isinstance(document.get('jails'), dict) else {}
        aggregate = jails.get('aggregate') if isinstance(jails.get('aggregate'), dict) else {}
        state = str(observation.get('state') or 'unavailable')
        detail = str(observation.get('detail') or 'Fail2ban live-state detail is unavailable.')
        observed = observation.get('jail_health_observed') is True

        if record['stale']:
            state = 'stale'
            detail = 'The Fail2ban live-state snapshot is stale; current jail health is not asserted.'
            observed = True
            append_once(warnings, 'fail2ban live-state snapshot is stale')
        elif state in {'inactive', 'partial'}:
            append_once(recommendations, 'Review the Fail2ban service and local control socket; observability did not change either one.')
        elif state in {'not_installed', 'unavailable'}:
            append_once(recommendations, 'Confirm whether Fail2ban is intended on Edge1 before planning any service or enforcement change.')

        components['fail2ban'] = BASE.BASE.component(
            'Fail2ban visibility',
            state,
            observed,
            False,
            detail,
            {
                'service_installed': service.get('installed') is True,
                'service_active': service.get('active') is True,
                'service_state': service.get('active_state'),
                'socket_reachable': client.get('socket_reachable') is True,
                'declared_jails': BASE.BASE.safe_int(jails.get('declared_count')),
                'observed_jails': BASE.BASE.safe_int(jails.get('observed_count')),
                'currently_failed': BASE.BASE.safe_int(aggregate.get('currently_failed')),
                'total_failed': BASE.BASE.safe_int(aggregate.get('total_failed')),
                'currently_banned': BASE.BASE.safe_int(aggregate.get('currently_banned')),
                'total_banned': BASE.BASE.safe_int(aggregate.get('total_banned')),
            },
        )

    old_limitation = 'DNS, general firewall, Fail2ban, and proxy enforcement remain unverified until dedicated sanitized status exporters exist.'
    limitations[:] = [item for item in limitations if item != old_limitation]
    append_once(limitations, 'DNS, general firewall, Fail2ban packet enforcement, and proxy enforcement remain unverified unless dedicated verification exists.')
    append_once(limitations, 'Fail2ban service and jail counters do not independently prove packet enforcement, action correctness, or every traffic path.')

    snapshot['schema_version'] = '1.2'
    privacy = snapshot.setdefault('privacy', {})
    privacy['fail2ban_banned_addresses_included'] = False
    privacy['fail2ban_raw_client_output_included'] = False

    summary = snapshot.setdefault('summary', {})
    summary['component_count'] = len(components)
    summary['observed_component_count'] = sum(1 for item in components.values() if item.get('observed'))
    summary['verified_enforcement_count'] = sum(1 for item in components.values() if item.get('enforcement_verified'))
    summary['source_count'] = len(sources)
    summary['available_source_count'] = sum(1 for item in sources.values() if item.get('available'))
    summary['stale_sources'] = [name for name, item in sources.items() if item.get('available') and item.get('stale')]
    return snapshot


def build_snapshot(
    network_path: Path = BASE.BASE.DEFAULT_NETWORK,
    security_path: Path = BASE.BASE.DEFAULT_SECURITY,
    correlation_path: Path = BASE.BASE.DEFAULT_CORRELATION,
    operations_path: Path = BASE.BASE.DEFAULT_OPERATIONS,
    spamhaus_path: Path = BASE.BASE.DEFAULT_SPAMHAUS,
    spamhaus_live_state_path: Path = BASE.BASE.DEFAULT_SPAMHAUS_LIVE_STATE,
    dns_policy_path: Path = BASE.DEFAULT_DNS_POLICY,
    fail2ban_live_state_path: Path = DEFAULT_FAIL2BAN_LIVE_STATE,
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    current = now or BASE.BASE.utc_now()
    snapshot = BASE.build_snapshot(
        network_path=network_path,
        security_path=security_path,
        correlation_path=correlation_path,
        operations_path=operations_path,
        spamhaus_path=spamhaus_path,
        spamhaus_live_state_path=spamhaus_live_state_path,
        dns_policy_path=dns_policy_path,
        now=current,
    )
    document, error = load_fail2ban(fail2ban_live_state_path)
    error = validate_fail2ban(document, error)
    return augment_snapshot(snapshot, document, error, fail2ban_live_state_path, current)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--network', type=Path, default=BASE.BASE.DEFAULT_NETWORK)
    parser.add_argument('--security', type=Path, default=BASE.BASE.DEFAULT_SECURITY)
    parser.add_argument('--correlation', type=Path, default=BASE.BASE.DEFAULT_CORRELATION)
    parser.add_argument('--operations', type=Path, default=BASE.BASE.DEFAULT_OPERATIONS)
    parser.add_argument('--spamhaus', type=Path, default=BASE.BASE.DEFAULT_SPAMHAUS)
    parser.add_argument('--spamhaus-live-state', type=Path, default=BASE.BASE.DEFAULT_SPAMHAUS_LIVE_STATE)
    parser.add_argument('--dns-policy', type=Path, default=BASE.DEFAULT_DNS_POLICY)
    parser.add_argument('--fail2ban-live-state', type=Path, default=DEFAULT_FAIL2BAN_LIVE_STATE)
    parser.add_argument('--output', type=Path, default=BASE.BASE.DEFAULT_OUTPUT)
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
    )
    BASE.BASE.write_snapshot(snapshot, args.output)
    print(json.dumps({
        'ok': True,
        'output': str(args.output),
        'overall_state': snapshot['overall_state'],
        'dns_policy_state': snapshot['components']['dns_policy']['state'],
        'spamhaus_state': snapshot['components']['spamhaus']['state'],
        'fail2ban_state': snapshot['components']['fail2ban']['state'],
        'verified_enforcement_count': snapshot['summary']['verified_enforcement_count'],
        'traffic_controls_changed': False,
    }))


if __name__ == '__main__':
    main()
