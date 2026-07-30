#!/usr/bin/env python3
"""Augment Network Defense with sanitized aggregate nftables topology and counters."""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
from pathlib import Path
from typing import Any

BASE_PATH = Path(__file__).with_name('network_defense_fail2ban_exporter.py')
SPEC = importlib.util.spec_from_file_location('network_defense_fail2ban', BASE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f'Unable to load Fail2ban-aware Network Defense exporter: {BASE_PATH}')
BASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BASE)

DEFAULT_NFTABLES_LIVE_STATE = Path('/var/lib/bigbird-networking/nftables/live-state.json')
NFTABLES_STALE_SECONDS = 5 * 60
CONTRACT = 'wwcx.nftables-aggregate-live-state.v1'
SUPPORTED_STATES = {'ruleset_observed', 'partial', 'empty', 'not_installed', 'unavailable'}


def load_nftables(path: Path) -> tuple[dict[str, Any], str | None]:
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return {}, 'nftables aggregate live-state source is missing'
    except (OSError, json.JSONDecodeError):
        return {}, 'nftables aggregate live-state source is unreadable'
    if not isinstance(value, dict):
        return {}, 'nftables aggregate live-state source is not a JSON object'
    return value, None


def validate_nftables(document: dict[str, Any], error: str | None) -> str | None:
    if error:
        return error
    if document.get('contract') != CONTRACT:
        return 'nftables aggregate live-state contract is unsupported'
    if document.get('read_only') is not True or document.get('traffic_controls_changed') is not False:
        return 'nftables aggregate live-state safety contract is invalid'
    privacy = document.get('privacy') if isinstance(document.get('privacy'), dict) else {}
    for key in (
        'addresses_included', 'interfaces_included', 'table_names_included',
        'chain_names_included', 'set_names_included', 'set_elements_included',
        'map_elements_included', 'rule_expressions_included', 'rule_comments_included',
        'rule_handles_included', 'full_ruleset_included', 'raw_command_output_included',
        'credentials_included', 'private_keys_included',
    ):
        if privacy.get(key) is not False:
            return 'nftables aggregate live-state privacy contract is invalid'
    observation = document.get('observation') if isinstance(document.get('observation'), dict) else {}
    if observation.get('enforcement_verified') is not False:
        return 'general nftables aggregate status must not claim enforcement verification'
    if observation.get('state') not in SUPPORTED_STATES:
        return 'nftables aggregate observation state is unsupported'
    if not isinstance(document.get('aggregates'), dict):
        return 'nftables aggregate counters are missing'
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
        'modified_at': BASE.BASE.BASE.iso(modified),
        'age_seconds': age_seconds,
        'stale_after_seconds': NFTABLES_STALE_SECONDS,
        'stale': age_seconds is None or age_seconds > NFTABLES_STALE_SECONDS,
        'detail': error or 'loaded',
    }


def append_once(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def safe_counts(value: Any, allowed: tuple[str, ...]) -> dict[str, int]:
    source = safe_dict(value)
    return {key: BASE.BASE.BASE.safe_int(source.get(key)) for key in allowed}


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
    sources['nftables_live_state'] = record

    old_recommendation = 'Publish normalized nftables counters and service posture without exposing the full ruleset.'
    recommendations[:] = [item for item in recommendations if item != old_recommendation]

    if error:
        append_once(warnings, error)
        append_once(recommendations, 'Restore the sanitized nftables aggregate source before relying on current ruleset posture.')
    else:
        observation = safe_dict(document.get('observation'))
        aggregates = safe_dict(document.get('aggregates'))
        objects = safe_dict(aggregates.get('objects'))
        base_chains = safe_dict(aggregates.get('base_chains'))
        rules = safe_dict(aggregates.get('rules'))
        elements = safe_dict(aggregates.get('elements'))
        counter_totals = safe_dict(aggregates.get('counter_totals'))
        service = safe_dict(document.get('service'))
        state = str(observation.get('state') or 'unavailable')
        detail = str(observation.get('detail') or 'nftables aggregate detail is unavailable.')
        observed = observation.get('observed') is True

        if record['stale']:
            state = 'stale'
            detail = 'The nftables aggregate snapshot is stale; current ruleset topology is not asserted.'
            observed = True
            append_once(warnings, 'nftables aggregate live-state snapshot is stale')
        elif state in {'partial', 'empty'}:
            append_once(recommendations, 'Review the nftables aggregate evidence before any separately authorized firewall change.')
        elif state in {'not_installed', 'unavailable'}:
            append_once(recommendations, 'Restore read-only nftables aggregate collection before evaluating general firewall posture.')

        components['firewall'] = BASE.BASE.BASE.component(
            'Firewall visibility',
            state,
            observed,
            False,
            detail,
            {
                'service_loaded': service.get('loaded') is True,
                'service_active_state': service.get('active_state'),
                'service_result': service.get('result'),
                'tables': BASE.BASE.BASE.safe_int(objects.get('table')),
                'chains': BASE.BASE.BASE.safe_int(objects.get('chain')),
                'base_chains': BASE.BASE.BASE.safe_int(base_chains.get('count')),
                'rules': BASE.BASE.BASE.safe_int(objects.get('rule')),
                'sets': BASE.BASE.BASE.safe_int(objects.get('set')),
                'maps': BASE.BASE.BASE.safe_int(objects.get('map')),
                'counter_objects': BASE.BASE.BASE.safe_int(objects.get('counter')),
                'set_elements': BASE.BASE.BASE.safe_int(elements.get('set_count')),
                'map_elements': BASE.BASE.BASE.safe_int(elements.get('map_count')),
                'rules_with_counters': BASE.BASE.BASE.safe_int(rules.get('with_counters')),
                'counter_packets': BASE.BASE.BASE.safe_int(counter_totals.get('packets')),
                'counter_bytes': BASE.BASE.BASE.safe_int(counter_totals.get('bytes')),
                'families': safe_counts(aggregates.get('families'), ('ip', 'ip6', 'inet', 'arp', 'bridge', 'netdev', 'other')),
                'hooks': safe_counts(base_chains.get('hooks'), ('prerouting', 'input', 'forward', 'output', 'postrouting', 'ingress', 'egress', 'other')),
                'policies': safe_counts(base_chains.get('policies'), ('accept', 'drop', 'other')),
                'verdicts': safe_counts(rules.get('verdicts'), ('accept', 'drop', 'reject', 'continue', 'return', 'jump', 'goto', 'queue')),
            },
        )

    old_limitation = 'DNS, general firewall, Fail2ban packet enforcement, and proxy enforcement remain unverified unless dedicated verification exists.'
    limitations[:] = [item for item in limitations if item != old_limitation]
    append_once(limitations, 'DNS, general firewall packet enforcement, Fail2ban packet enforcement, and proxy enforcement remain unverified unless dedicated verification exists.')
    append_once(limitations, 'General nftables topology and counters do not prove policy correctness, packet-path coverage, or intended enforcement behavior.')

    snapshot['schema_version'] = '1.3'
    privacy = snapshot.setdefault('privacy', {})
    privacy['firewall_addresses_included'] = False
    privacy['firewall_interfaces_included'] = False
    privacy['firewall_names_included'] = False
    privacy['firewall_rule_expressions_included'] = False
    privacy['firewall_comments_included'] = False
    privacy['firewall_handles_included'] = False

    summary = snapshot.setdefault('summary', {})
    summary['component_count'] = len(components)
    summary['observed_component_count'] = sum(1 for item in components.values() if item.get('observed'))
    summary['verified_enforcement_count'] = sum(1 for item in components.values() if item.get('enforcement_verified'))
    summary['source_count'] = len(sources)
    summary['available_source_count'] = sum(1 for item in sources.values() if item.get('available'))
    summary['stale_sources'] = [name for name, item in sources.items() if item.get('available') and item.get('stale')]
    return snapshot


def build_snapshot(
    network_path: Path = BASE.BASE.BASE.DEFAULT_NETWORK,
    security_path: Path = BASE.BASE.BASE.DEFAULT_SECURITY,
    correlation_path: Path = BASE.BASE.BASE.DEFAULT_CORRELATION,
    operations_path: Path = BASE.BASE.BASE.DEFAULT_OPERATIONS,
    spamhaus_path: Path = BASE.BASE.BASE.DEFAULT_SPAMHAUS,
    spamhaus_live_state_path: Path = BASE.BASE.BASE.DEFAULT_SPAMHAUS_LIVE_STATE,
    dns_policy_path: Path = BASE.BASE.DEFAULT_DNS_POLICY,
    fail2ban_live_state_path: Path = BASE.DEFAULT_FAIL2BAN_LIVE_STATE,
    nftables_live_state_path: Path = DEFAULT_NFTABLES_LIVE_STATE,
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    current = now or BASE.BASE.BASE.utc_now()
    snapshot = BASE.build_snapshot(
        network_path=network_path,
        security_path=security_path,
        correlation_path=correlation_path,
        operations_path=operations_path,
        spamhaus_path=spamhaus_path,
        spamhaus_live_state_path=spamhaus_live_state_path,
        dns_policy_path=dns_policy_path,
        fail2ban_live_state_path=fail2ban_live_state_path,
        now=current,
    )
    document, error = load_nftables(nftables_live_state_path)
    error = validate_nftables(document, error)
    return augment_snapshot(snapshot, document, error, nftables_live_state_path, current)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--network', type=Path, default=BASE.BASE.BASE.DEFAULT_NETWORK)
    parser.add_argument('--security', type=Path, default=BASE.BASE.BASE.DEFAULT_SECURITY)
    parser.add_argument('--correlation', type=Path, default=BASE.BASE.BASE.DEFAULT_CORRELATION)
    parser.add_argument('--operations', type=Path, default=BASE.BASE.BASE.DEFAULT_OPERATIONS)
    parser.add_argument('--spamhaus', type=Path, default=BASE.BASE.BASE.DEFAULT_SPAMHAUS)
    parser.add_argument('--spamhaus-live-state', type=Path, default=BASE.BASE.BASE.DEFAULT_SPAMHAUS_LIVE_STATE)
    parser.add_argument('--dns-policy', type=Path, default=BASE.BASE.DEFAULT_DNS_POLICY)
    parser.add_argument('--fail2ban-live-state', type=Path, default=BASE.DEFAULT_FAIL2BAN_LIVE_STATE)
    parser.add_argument('--nftables-live-state', type=Path, default=DEFAULT_NFTABLES_LIVE_STATE)
    parser.add_argument('--output', type=Path, default=BASE.BASE.BASE.DEFAULT_OUTPUT)
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
    BASE.BASE.BASE.write_snapshot(snapshot, args.output)
    print(json.dumps({
        'ok': True,
        'output': str(args.output),
        'overall_state': snapshot['overall_state'],
        'firewall_state': snapshot['components']['firewall']['state'],
        'fail2ban_state': snapshot['components']['fail2ban']['state'],
        'spamhaus_state': snapshot['components']['spamhaus']['state'],
        'verified_enforcement_count': snapshot['summary']['verified_enforcement_count'],
        'traffic_controls_changed': False,
    }))


if __name__ == '__main__':
    main()
