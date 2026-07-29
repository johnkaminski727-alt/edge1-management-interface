#!/usr/bin/env python3
"""Build a sanitized, read-only Edge1 network-defense observability snapshot."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
from typing import Any, Iterable

DEFAULT_NETWORK = Path('/var/www/edge1-status/operations-network.json')
DEFAULT_SECURITY = Path('/var/www/edge1-status/security-operations.json')
DEFAULT_CORRELATION = Path('/var/www/edge1-status/security-correlation.json')
DEFAULT_OPERATIONS = Path('/var/lib/bigbird/operations-center/latest.json')
DEFAULT_SPAMHAUS = Path('/var/lib/bigbird-networking/spamhaus/summary.txt')
DEFAULT_SPAMHAUS_LIVE_STATE = Path('/var/lib/bigbird-networking/spamhaus/live-state.json')
DEFAULT_OUTPUT = Path('/var/www/edge1-status/network-defense.json')

SOURCE_STALE_SECONDS = {
    'network': 5 * 60,
    'security': 5 * 60,
    'correlation': 5 * 60,
    'operations': 5 * 60,
    'spamhaus': 8 * 60 * 60,
    'spamhaus_live_state': 5 * 60,
}


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso(value: dt.datetime | None) -> str | None:
    return value.astimezone(dt.timezone.utc).isoformat() if value else None


def load_json(path: Path, source_name: str) -> tuple[dict[str, Any], str | None]:
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return {}, f'{source_name} source is missing'
    except (OSError, json.JSONDecodeError):
        return {}, f'{source_name} source is unreadable'
    if not isinstance(value, dict):
        return {}, f'{source_name} source is not a JSON object'
    return value, None


def parse_spamhaus(path: Path) -> tuple[dict[str, int], str | None]:
    try:
        lines = path.read_text(encoding='utf-8').splitlines()
    except FileNotFoundError:
        return {}, 'spamhaus source is missing'
    except OSError:
        return {}, 'spamhaus source is unreadable'

    allowed = {'drop4', 'edrop4', 'combined4', 'drop6'}
    values: dict[str, int] = {}
    for line in lines:
        key, separator, raw = line.partition('=')
        if not separator or key.strip() not in allowed:
            continue
        try:
            values[key.strip()] = max(0, int(raw.strip()))
        except ValueError:
            continue
    if not values:
        return {}, 'spamhaus source has no recognized counters'
    return values, None


def validate_spamhaus_live_state(document: dict[str, Any], error: str | None) -> str | None:
    if error:
        return error
    if document.get('contract') != 'wwcx.spamhaus-live-state.v1':
        return 'spamhaus live-state contract is unsupported'
    if document.get('read_only') is not True or document.get('traffic_controls_changed') is not False:
        return 'spamhaus live-state safety contract is invalid'
    privacy = document.get('privacy') if isinstance(document.get('privacy'), dict) else {}
    for key in ('addresses_included', 'set_elements_included', 'full_ruleset_included', 'raw_command_output_included'):
        if privacy.get(key) is not False:
            return 'spamhaus live-state privacy contract is invalid'
    if not isinstance(document.get('enforcement'), dict):
        return 'spamhaus live-state enforcement record is missing'
    return None


def source_record(path: Path, source_name: str, error: str | None, now: dt.datetime) -> dict[str, Any]:
    modified: dt.datetime | None = None
    try:
        modified = dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc)
    except OSError:
        pass
    age_seconds = int(max(0, (now - modified).total_seconds())) if modified else None
    stale_after = SOURCE_STALE_SECONDS[source_name]
    return {
        'available': error is None,
        'file': path.name,
        'modified_at': iso(modified),
        'age_seconds': age_seconds,
        'stale_after_seconds': stale_after,
        'stale': age_seconds is None or age_seconds > stale_after,
        'detail': error or 'loaded',
    }


def find_lists(document: Any, candidate_keys: Iterable[str]) -> list[dict[str, Any]]:
    keys = set(candidate_keys)
    matches: list[dict[str, Any]] = []

    def walk(value: Any, depth: int) -> None:
        if depth > 5:
            return
        if isinstance(value, dict):
            for key, child in value.items():
                if key in keys and isinstance(child, list):
                    matches.extend(item for item in child if isinstance(item, dict))
                elif isinstance(child, (dict, list)):
                    walk(child, depth + 1)
        elif isinstance(value, list):
            for child in value[:200]:
                if isinstance(child, (dict, list)):
                    walk(child, depth + 1)

    walk(document, 0)
    return matches[:500]


def safe_int(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def count_category(correlation: dict[str, Any], operations: dict[str, Any], category: str) -> int:
    summary = correlation.get('summary') if isinstance(correlation.get('summary'), dict) else {}
    counts = summary.get('category_counts') if isinstance(summary.get('category_counts'), dict) else {}
    value = counts.get(category)
    if isinstance(value, (int, float)):
        return max(0, int(value))
    key_map = {
        'dns': ('recent_dns_queries', 'dns_queries', 'dns_events'),
        'firewall': ('recent_firewall_events', 'firewall_events', 'nftables_events', 'drops'),
        'fail2ban': ('recent_fail2ban_events', 'fail2ban_events', 'bans'),
        'proxy': ('recent_proxy_events', 'proxy_events', 'squid_events'),
    }
    return len(find_lists(operations, key_map.get(category, ())))


def component(name: str, state: str, observed: bool, enforcement_verified: bool, detail: str, metrics: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        'name': name,
        'state': state,
        'observed': observed,
        'enforcement_verified': enforcement_verified,
        'detail': detail,
        'metrics': metrics or {},
    }


def build_snapshot(
    network_path: Path = DEFAULT_NETWORK,
    security_path: Path = DEFAULT_SECURITY,
    correlation_path: Path = DEFAULT_CORRELATION,
    operations_path: Path = DEFAULT_OPERATIONS,
    spamhaus_path: Path = DEFAULT_SPAMHAUS,
    spamhaus_live_state_path: Path = DEFAULT_SPAMHAUS_LIVE_STATE,
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    current = now or utc_now()
    warnings: list[str] = []

    network, network_error = load_json(network_path, 'network')
    security, security_error = load_json(security_path, 'security')
    correlation, correlation_error = load_json(correlation_path, 'correlation')
    operations, operations_error = load_json(operations_path, 'operations')
    spamhaus, spamhaus_error = parse_spamhaus(spamhaus_path)
    spamhaus_live_state, spamhaus_live_error = load_json(spamhaus_live_state_path, 'spamhaus live-state')
    spamhaus_live_error = validate_spamhaus_live_state(spamhaus_live_state, spamhaus_live_error)

    errors = {
        'network': network_error,
        'security': security_error,
        'correlation': correlation_error,
        'operations': operations_error,
        'spamhaus': spamhaus_error,
        'spamhaus_live_state': spamhaus_live_error,
    }
    warnings.extend(error for error in errors.values() if error)

    sources = {
        name: source_record(path, name, errors[name], current)
        for name, path in (
            ('network', network_path),
            ('security', security_path),
            ('correlation', correlation_path),
            ('operations', operations_path),
            ('spamhaus', spamhaus_path),
            ('spamhaus_live_state', spamhaus_live_state_path),
        )
    }

    alerts = security.get('recent_alerts') if isinstance(security.get('recent_alerts'), list) else []
    health = security.get('health') if isinstance(security.get('health'), dict) else {}
    engine = security.get('engine') if isinstance(security.get('engine'), dict) else {}
    ids_observed = security_error is None and bool(health or engine or alerts)
    ids_state = 'healthy' if str(health.get('status', '')).lower() == 'healthy' else ('observed' if ids_observed else 'unavailable')

    resolver_text = network.get('resolver')
    dns_events = count_category(correlation, operations, 'dns')
    dns_observed = bool(resolver_text) or dns_events > 0

    firewall_events = count_category(correlation, operations, 'firewall')
    fail2ban_events = count_category(correlation, operations, 'fail2ban')
    proxy_events = count_category(correlation, operations, 'proxy')

    combined4 = safe_int(spamhaus.get('combined4'))
    drop6 = safe_int(spamhaus.get('drop6'))
    spamhaus_feed_observed = spamhaus_error is None and (combined4 > 0 or drop6 > 0)

    enforcement = spamhaus_live_state.get('enforcement') if isinstance(spamhaus_live_state.get('enforcement'), dict) else {}
    table = spamhaus_live_state.get('table') if isinstance(spamhaus_live_state.get('table'), dict) else {}
    sets = spamhaus_live_state.get('sets') if isinstance(spamhaus_live_state.get('sets'), dict) else {}
    rules = spamhaus_live_state.get('rules') if isinstance(spamhaus_live_state.get('rules'), dict) else {}
    service = spamhaus_live_state.get('service') if isinstance(spamhaus_live_state.get('service'), dict) else {}
    timer = spamhaus_live_state.get('timer') if isinstance(spamhaus_live_state.get('timer'), dict) else {}
    spamhaus_verified = spamhaus_live_error is None and enforcement.get('verified') is True
    spamhaus_table_observed = spamhaus_live_error is None and table.get('present') is True
    spamhaus_observed = spamhaus_feed_observed or spamhaus_table_observed

    if spamhaus_verified:
        spamhaus_state = 'active_verified'
        spamhaus_detail = 'Spamhaus feed counters and the dedicated nftables table, drop sets, hooked rules, updater result, and timer are verified.'
    elif spamhaus_feed_observed:
        spamhaus_state = 'feed_ready'
        spamhaus_detail = 'Spamhaus feed counters are present, but the complete live nftables enforcement contract is not verified.'
    elif spamhaus_table_observed:
        spamhaus_state = str(enforcement.get('state') or 'partial')
        spamhaus_detail = str(enforcement.get('detail') or 'The live Spamhaus table is partially observed.')
    else:
        spamhaus_state = 'unavailable'
        spamhaus_detail = 'Spamhaus feed and live-state evidence are unavailable.'

    drop4_set = sets.get('drop4') if isinstance(sets.get('drop4'), dict) else {}
    drop6_set = sets.get('drop6') if isinstance(sets.get('drop6'), dict) else {}

    components = {
        'ids': component(
            'Intrusion detection', ids_state, ids_observed, False,
            'Suricata security telemetry is available.' if ids_observed else 'No IDS telemetry is available.',
            {'recent_alerts': len(alerts), 'engine_version': engine.get('version')},
        ),
        'dns': component(
            'DNS visibility', 'observed' if dns_observed else 'not_observed', dns_observed, False,
            'Resolver or DNS-event telemetry is visible; policy enforcement is not verified.' if dns_observed else 'No shared DNS policy telemetry is available.',
            {'recent_events': dns_events, 'resolver_reported': bool(resolver_text)},
        ),
        'spamhaus': component(
            'Network reputation', spamhaus_state, spamhaus_observed, spamhaus_verified,
            spamhaus_detail,
            {
                'combined_ipv4_networks': combined4,
                'ipv6_networks': drop6,
                'table_present': table.get('present') is True,
                'drop4_elements': safe_int(drop4_set.get('element_count')),
                'drop6_elements': safe_int(drop6_set.get('element_count')),
                'input_ipv4_drop_rules': safe_int(rules.get('input_ipv4_drop')),
                'forward_ipv4_drop_rules': safe_int(rules.get('forward_ipv4_drop')),
                'input_ipv6_drop_rules': safe_int(rules.get('input_ipv6_drop')),
                'forward_ipv6_drop_rules': safe_int(rules.get('forward_ipv6_drop')),
                'service_result': service.get('result'),
                'timer_active': timer.get('active_state'),
                'timer_enabled': timer.get('enabled_state'),
            },
        ),
        'firewall': component(
            'Firewall visibility', 'observed' if firewall_events else 'not_observed', firewall_events > 0, False,
            'Firewall events are visible; active ruleset posture is not verified.' if firewall_events else 'No normalized firewall-event telemetry is available.',
            {'recent_events': firewall_events},
        ),
        'fail2ban': component(
            'Fail2ban visibility', 'observed' if fail2ban_events else 'not_observed', fail2ban_events > 0, False,
            'Fail2ban events are visible; jail configuration and service state are not verified.' if fail2ban_events else 'No normalized Fail2ban telemetry is available.',
            {'recent_events': fail2ban_events},
        ),
        'proxy': component(
            'Proxy visibility', 'observed' if proxy_events else 'not_configured', proxy_events > 0, False,
            'Proxy events are visible; enforcement is not verified.' if proxy_events else 'No Squid or other proxy telemetry is configured in the shared status contract.',
            {'recent_events': proxy_events},
        ),
    }

    observed_count = sum(1 for item in components.values() if item['observed'])
    stale_sources = [name for name, item in sources.items() if item['available'] and item['stale']]
    unavailable_sources = [name for name, item in sources.items() if not item['available']]
    if unavailable_sources:
        overall = 'limited'
    elif stale_sources:
        overall = 'stale'
    elif observed_count >= 3:
        overall = 'observed'
    else:
        overall = 'limited'

    recommendations: list[str] = []
    if not components['dns']['observed']:
        recommendations.append('Define a sanitized DNS status contract before evaluating RPZ or local-zone enforcement.')
    if not components['firewall']['observed']:
        recommendations.append('Publish normalized nftables counters and service posture without exposing the full ruleset.')
    if not components['fail2ban']['observed']:
        recommendations.append('Publish Fail2ban jail health and aggregate ban counts without client-identifying log content.')
    if not components['proxy']['observed']:
        recommendations.append('Complete the Squid/proxy architecture decision before installing or routing traffic through a proxy.')
    if spamhaus_feed_observed and not spamhaus_verified:
        recommendations.append('Restore the Spamhaus live-state verifier contract so feed readiness can be distinguished from active enforcement.')

    limitations = [
        'This snapshot reports bounded current-state evidence and does not expose the full firewall ruleset or set elements.',
        'DNS, general firewall, Fail2ban, and proxy enforcement remain unverified until dedicated sanitized status exporters exist.',
    ]
    if spamhaus_verified:
        limitations.append('Spamhaus verification proves the expected table, sets, hooked rules, service result, and timer at snapshot time; it does not prove every possible traffic path traverses those hooks.')
    else:
        limitations.append('Spamhaus feed counters do not independently verify the live nftables table or service result.')

    return {
        'schema_version': '1.1',
        'generated_at': iso(current),
        'read_only': True,
        'traffic_controls_changed': False,
        'privacy': {
            'packet_payloads_included': False,
            'credentials_included': False,
            'private_keys_included': False,
            'raw_logs_included': False,
            'full_firewall_ruleset_included': False,
            'firewall_set_elements_included': False,
        },
        'overall_state': overall,
        'summary': {
            'component_count': len(components),
            'observed_component_count': observed_count,
            'verified_enforcement_count': sum(1 for item in components.values() if item['enforcement_verified']),
            'available_source_count': sum(1 for item in sources.values() if item['available']),
            'source_count': len(sources),
            'stale_sources': stale_sources,
        },
        'sources': sources,
        'components': components,
        'correlation_context': {
            'event_count': safe_int((correlation.get('summary') or {}).get('event_count')) if isinstance(correlation.get('summary'), dict) else 0,
            'correlation_count': safe_int((correlation.get('summary') or {}).get('correlation_count')) if isinstance(correlation.get('summary'), dict) else 0,
            'high_confidence_count': safe_int((correlation.get('summary') or {}).get('high_confidence_count')) if isinstance(correlation.get('summary'), dict) else 0,
        },
        'warnings': warnings,
        'recommendations': recommendations,
        'limitations': limitations,
    }


def write_snapshot(snapshot: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + '.tmp')
    temporary.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    os.chmod(temporary, 0o644)
    temporary.replace(output)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--network', type=Path, default=DEFAULT_NETWORK)
    parser.add_argument('--security', type=Path, default=DEFAULT_SECURITY)
    parser.add_argument('--correlation', type=Path, default=DEFAULT_CORRELATION)
    parser.add_argument('--operations', type=Path, default=DEFAULT_OPERATIONS)
    parser.add_argument('--spamhaus', type=Path, default=DEFAULT_SPAMHAUS)
    parser.add_argument('--spamhaus-live-state', type=Path, default=DEFAULT_SPAMHAUS_LIVE_STATE)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
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
    )
    write_snapshot(snapshot, args.output)
    print(json.dumps({
        'ok': True,
        'output': str(args.output),
        'overall_state': snapshot['overall_state'],
        'observed_components': snapshot['summary']['observed_component_count'],
        'verified_enforcement_count': snapshot['summary']['verified_enforcement_count'],
    }))


if __name__ == '__main__':
    main()
