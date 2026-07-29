#!/usr/bin/env python3
"""Augment the read-only Network Defense snapshot with staged DNS policy readiness."""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
from pathlib import Path
from typing import Any

BASE_PATH = Path(__file__).with_name('network_defense_exporter.py')
SPEC = importlib.util.spec_from_file_location('network_defense_base', BASE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f'Unable to load Network Defense exporter: {BASE_PATH}')
BASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BASE)

DEFAULT_DNS_POLICY = Path('/var/www/edge1-status/dns-defense-policy-status.json')
DNS_POLICY_STALE_SECONDS = 24 * 60 * 60


def load_dns_policy(path: Path) -> tuple[dict[str, Any], str | None]:
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return {}, 'dns policy status is not staged'
    except (OSError, json.JSONDecodeError):
        return {}, 'dns policy status is unreadable'
    if not isinstance(value, dict):
        return {}, 'dns policy status is not a JSON object'
    return value, None


def dns_source_record(path: Path, error: str | None, now: dt.datetime) -> dict[str, Any]:
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
        'modified_at': BASE.iso(modified),
        'age_seconds': age_seconds,
        'stale_after_seconds': DNS_POLICY_STALE_SECONDS,
        'stale': age_seconds is None or age_seconds > DNS_POLICY_STALE_SECONDS,
        'detail': error or 'loaded',
    }


def safe_policy_summary(document: dict[str, Any]) -> dict[str, Any]:
    policy = document.get('policy') if isinstance(document.get('policy'), dict) else {}
    action_counts = policy.get('action_counts') if isinstance(policy.get('action_counts'), dict) else {}
    return {
        'name': str(policy.get('name') or ''),
        'serial': BASE.safe_int(policy.get('serial')),
        'entry_count': BASE.safe_int(policy.get('entry_count')),
        'expanded_record_count': BASE.safe_int(policy.get('expanded_record_count')),
        'action_counts': {
            key: BASE.safe_int(action_counts.get(key))
            for key in ('nxdomain', 'nodata', 'passthru')
        },
    }


def augment_snapshot(
    snapshot: dict[str, Any],
    policy_document: dict[str, Any],
    policy_error: str | None,
    policy_path: Path,
    now: dt.datetime,
) -> dict[str, Any]:
    sources = snapshot.setdefault('sources', {})
    components = snapshot.setdefault('components', {})
    recommendations = snapshot.setdefault('recommendations', [])
    warnings = snapshot.setdefault('warnings', [])
    limitations = snapshot.setdefault('limitations', [])

    sources['dns_policy'] = dns_source_record(policy_path, policy_error, now)
    policy = safe_policy_summary(policy_document)
    activation_mode = str(policy_document.get('activation_mode') or 'not_staged')
    enforcement_enabled = policy_document.get('enforcement_enabled') is True
    traffic_changed = policy_document.get('traffic_controls_changed') is True
    override = str(policy_document.get('rpz_action_override') or '')
    safely_staged = (
        policy_error is None
        and activation_mode == 'staged_disabled'
        and not enforcement_enabled
        and not traffic_changed
        and override == 'disabled'
    )

    if policy_error:
        state = 'not_staged'
        detail = 'No staged DNS policy status is available; resolver behavior is unchanged.'
        recommendations.append('Compile and publish a disabled DNS policy staging snapshot before any resolver activation review.')
    elif safely_staged:
        state = 'staged_disabled'
        detail = 'An RPZ policy is staged with actions disabled; resolver enforcement is not active or verified.'
    else:
        state = 'unverified'
        detail = 'DNS policy status exists but does not satisfy the disabled staging safety contract.'
        warnings.append('dns policy status does not satisfy the staged-disabled safety contract')
        recommendations.append('Restore staged_disabled, rpz-action-override disabled, and traffic_controls_changed false before review.')

    components['dns_policy'] = BASE.component(
        'DNS policy readiness',
        state,
        policy_error is None,
        False,
        detail,
        {
            'policy_name': policy['name'],
            'serial': policy['serial'],
            'entry_count': policy['entry_count'],
            'expanded_record_count': policy['expanded_record_count'],
            'action_counts': policy['action_counts'],
            'activation_mode': activation_mode,
            'enforcement_enabled': enforcement_enabled,
            'rpz_action_override': override or None,
        },
    )

    snapshot['dns_policy'] = {
        'status_available': policy_error is None,
        'policy_staged': safely_staged,
        'activation_mode': activation_mode,
        'enforcement_enabled': False,
        'enforcement_verified': False,
        'traffic_controls_changed': False,
        'requires_explicit_activation': True,
        'policy': policy,
    }

    summary = snapshot.setdefault('summary', {})
    summary['component_count'] = len(components)
    summary['observed_component_count'] = sum(1 for item in components.values() if item.get('observed'))
    summary['verified_enforcement_count'] = sum(1 for item in components.values() if item.get('enforcement_verified'))
    summary['source_count'] = len(sources)
    summary['available_source_count'] = sum(1 for item in sources.values() if item.get('available'))
    summary['stale_sources'] = [name for name, item in sources.items() if item.get('available') and item.get('stale')]

    limitation = 'DNS policy staging evidence does not prove that Unbound loaded the RPZ or that filtering is active.'
    if limitation not in limitations:
        limitations.append(limitation)
    return snapshot


def build_snapshot(
    network_path: Path = BASE.DEFAULT_NETWORK,
    security_path: Path = BASE.DEFAULT_SECURITY,
    correlation_path: Path = BASE.DEFAULT_CORRELATION,
    operations_path: Path = BASE.DEFAULT_OPERATIONS,
    spamhaus_path: Path = BASE.DEFAULT_SPAMHAUS,
    dns_policy_path: Path = DEFAULT_DNS_POLICY,
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    current = now or BASE.utc_now()
    snapshot = BASE.build_snapshot(
        network_path=network_path,
        security_path=security_path,
        correlation_path=correlation_path,
        operations_path=operations_path,
        spamhaus_path=spamhaus_path,
        now=current,
    )
    policy, policy_error = load_dns_policy(dns_policy_path)
    return augment_snapshot(snapshot, policy, policy_error, dns_policy_path, current)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--network', type=Path, default=BASE.DEFAULT_NETWORK)
    parser.add_argument('--security', type=Path, default=BASE.DEFAULT_SECURITY)
    parser.add_argument('--correlation', type=Path, default=BASE.DEFAULT_CORRELATION)
    parser.add_argument('--operations', type=Path, default=BASE.DEFAULT_OPERATIONS)
    parser.add_argument('--spamhaus', type=Path, default=BASE.DEFAULT_SPAMHAUS)
    parser.add_argument('--dns-policy', type=Path, default=DEFAULT_DNS_POLICY)
    parser.add_argument('--output', type=Path, default=BASE.DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    snapshot = build_snapshot(
        network_path=args.network,
        security_path=args.security,
        correlation_path=args.correlation,
        operations_path=args.operations,
        spamhaus_path=args.spamhaus,
        dns_policy_path=args.dns_policy,
    )
    BASE.write_snapshot(snapshot, args.output)
    print(json.dumps({
        'ok': True,
        'output': str(args.output),
        'overall_state': snapshot['overall_state'],
        'dns_policy_state': snapshot['components']['dns_policy']['state'],
        'enforcement_enabled': False,
    }))


if __name__ == '__main__':
    main()
