#!/usr/bin/env python3
"""Publish sanitized read-only evidence for the live Big Bird Spamhaus nftables filter."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Callable, Sequence

DEFAULT_OUTPUT = Path('/var/lib/bigbird-networking/spamhaus/live-state.json')
DEFAULT_NFT = Path('/usr/sbin/nft')
DEFAULT_SYSTEMCTL = Path('/usr/bin/systemctl')
TABLE_FAMILY = 'inet'
TABLE_NAME = 'bigbird_spamhaus'
SERVICE_NAME = 'bigbird-spamhaus-filter.service'
TIMER_NAME = 'bigbird-spamhaus-filter.timer'
SCHEMA_VERSION = 'wwcx.spamhaus-live-state.v1'

CommandRunner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).isoformat()


def default_runner(args: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )


def parse_systemctl_show(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in text.splitlines():
        key, separator, value = raw.partition('=')
        if separator and key:
            values[key] = value
    return values


def contains_token(value: Any, token: str) -> bool:
    if isinstance(value, str):
        return value == token
    if isinstance(value, dict):
        return any(contains_token(key, token) or contains_token(child, token) for key, child in value.items())
    if isinstance(value, list):
        return any(contains_token(child, token) for child in value)
    return False


def contains_drop(value: Any) -> bool:
    if isinstance(value, dict):
        if 'drop' in value:
            return True
        return any(contains_drop(child) for child in value.values())
    if isinstance(value, list):
        return any(contains_drop(child) for child in value)
    return False


def element_count(value: Any) -> int:
    return len(value) if isinstance(value, list) else 0


def parse_nft_document(document: dict[str, Any]) -> dict[str, Any]:
    records = document.get('nftables') if isinstance(document.get('nftables'), list) else []
    table_present = False
    sets: dict[str, dict[str, Any]] = {}
    chains: dict[str, dict[str, Any]] = {}
    rule_counts = {
        'input_ipv4_drop': 0,
        'forward_ipv4_drop': 0,
        'input_ipv6_drop': 0,
        'forward_ipv6_drop': 0,
    }

    for record in records:
        if not isinstance(record, dict):
            continue
        table = record.get('table')
        if isinstance(table, dict) and table.get('family') == TABLE_FAMILY and table.get('name') == TABLE_NAME:
            table_present = True

        nft_set = record.get('set')
        if isinstance(nft_set, dict) and nft_set.get('family') == TABLE_FAMILY and nft_set.get('table') == TABLE_NAME:
            name = str(nft_set.get('name') or '')
            if name in {'drop4', 'drop6'}:
                sets[name] = {
                    'present': True,
                    'element_count': element_count(nft_set.get('elem')),
                    'interval': 'interval' in (nft_set.get('flags') or []),
                }

        chain = record.get('chain')
        if isinstance(chain, dict) and chain.get('family') == TABLE_FAMILY and chain.get('table') == TABLE_NAME:
            name = str(chain.get('name') or '')
            if name in {'input', 'forward'}:
                chains[name] = {
                    'present': True,
                    'hook': chain.get('hook'),
                    'policy': chain.get('policy'),
                    'priority': chain.get('prio', chain.get('priority')),
                }

        rule = record.get('rule')
        if not isinstance(rule, dict) or rule.get('family') != TABLE_FAMILY or rule.get('table') != TABLE_NAME:
            continue
        chain_name = str(rule.get('chain') or '')
        if chain_name not in {'input', 'forward'} or not contains_drop(rule.get('expr')):
            continue
        if contains_token(rule.get('expr'), '@drop4'):
            rule_counts[f'{chain_name}_ipv4_drop'] += 1
        if contains_token(rule.get('expr'), '@drop6'):
            rule_counts[f'{chain_name}_ipv6_drop'] += 1

    for name in ('drop4', 'drop6'):
        sets.setdefault(name, {'present': False, 'element_count': 0, 'interval': False})
    for name in ('input', 'forward'):
        chains.setdefault(name, {'present': False, 'hook': None, 'policy': None, 'priority': None})

    return {
        'table_present': table_present,
        'sets': sets,
        'chains': chains,
        'rules': rule_counts,
    }


def build_snapshot(
    nft_document: dict[str, Any] | None,
    nft_error: str | None,
    service: dict[str, str],
    timer_active: str,
    timer_enabled: str,
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    current = now or utc_now()
    parsed = parse_nft_document(nft_document or {})
    sets = parsed['sets']
    chains = parsed['chains']
    rules = parsed['rules']

    service_success = service.get('Result') == 'success' and service.get('ExecMainStatus') == '0'
    timer_ready = timer_active == 'active' and timer_enabled in {'enabled', 'enabled-runtime'}
    ipv4_verified = (
        parsed['table_present']
        and sets['drop4']['present']
        and sets['drop4']['element_count'] > 0
        and chains['input']['present']
        and chains['forward']['present']
        and rules['input_ipv4_drop'] > 0
        and rules['forward_ipv4_drop'] > 0
    )
    ipv6_required = sets['drop6']['present'] and sets['drop6']['element_count'] > 0
    ipv6_verified = (
        not ipv6_required
        or (
            rules['input_ipv6_drop'] > 0
            and rules['forward_ipv6_drop'] > 0
        )
    )
    verified = nft_error is None and ipv4_verified and ipv6_verified and service_success and timer_ready

    if verified:
        state = 'active_verified'
        detail = 'The dedicated Spamhaus nftables table, drop sets, hooked drop rules, successful updater result, and active timer were observed.'
    elif nft_error:
        state = 'unavailable'
        detail = 'The live nftables table could not be inspected.'
    elif not parsed['table_present']:
        state = 'not_present'
        detail = 'The expected Spamhaus nftables table is not present.'
    else:
        state = 'partial'
        detail = 'Some Spamhaus filter assets are present, but the complete live-state contract was not verified.'

    errors: list[str] = []
    if nft_error:
        errors.append(nft_error)
    if not service_success:
        errors.append('filter service result is not success')
    if not timer_ready:
        errors.append('filter timer is not active and enabled')
    if parsed['table_present'] and not ipv4_verified:
        errors.append('IPv4 set or hooked drop rules are incomplete')
    if ipv6_required and not ipv6_verified:
        errors.append('IPv6 set is populated but hooked drop rules are incomplete')

    return {
        'schema_version': '1.0',
        'contract': SCHEMA_VERSION,
        'generated_at': iso(current),
        'read_only': True,
        'traffic_controls_changed': False,
        'privacy': {
            'addresses_included': False,
            'set_elements_included': False,
            'full_ruleset_included': False,
            'raw_command_output_included': False,
            'credentials_included': False,
            'private_keys_included': False,
        },
        'expected': {
            'table_family': TABLE_FAMILY,
            'table_name': TABLE_NAME,
            'service': SERVICE_NAME,
            'timer': TIMER_NAME,
        },
        'table': {
            'present': parsed['table_present'],
            'family': TABLE_FAMILY,
            'name': TABLE_NAME,
        },
        'sets': sets,
        'chains': chains,
        'rules': rules,
        'service': {
            'result': service.get('Result') or 'unknown',
            'exec_main_status': service.get('ExecMainStatus') or 'unknown',
            'active_state': service.get('ActiveState') or 'unknown',
            'sub_state': service.get('SubState') or 'unknown',
            'success': service_success,
        },
        'timer': {
            'active_state': timer_active,
            'enabled_state': timer_enabled,
            'ready': timer_ready,
        },
        'enforcement': {
            'state': state,
            'verified': verified,
            'ipv4_verified': ipv4_verified,
            'ipv6_required': ipv6_required,
            'ipv6_verified': ipv6_verified,
            'detail': detail,
        },
        'errors': errors,
    }


def collect_live_state(
    nft_path: Path = DEFAULT_NFT,
    systemctl_path: Path = DEFAULT_SYSTEMCTL,
    runner: CommandRunner = default_runner,
) -> dict[str, Any]:
    nft_result = runner([str(nft_path), '-j', 'list', 'table', TABLE_FAMILY, TABLE_NAME])
    nft_document: dict[str, Any] | None = None
    nft_error: str | None = None
    if nft_result.returncode == 0:
        try:
            value = json.loads(nft_result.stdout)
            if not isinstance(value, dict):
                raise ValueError('not an object')
            nft_document = value
        except (json.JSONDecodeError, ValueError):
            nft_error = 'nftables response is not valid JSON'
    else:
        nft_error = 'expected Spamhaus nftables table is unavailable'

    service_result = runner([
        str(systemctl_path), 'show', SERVICE_NAME,
        '--property=Result', '--property=ExecMainStatus',
        '--property=ActiveState', '--property=SubState',
    ])
    service = parse_systemctl_show(service_result.stdout) if service_result.returncode == 0 else {}

    active_result = runner([str(systemctl_path), 'is-active', TIMER_NAME])
    timer_active = active_result.stdout.strip() or 'unknown'
    enabled_result = runner([str(systemctl_path), 'is-enabled', TIMER_NAME])
    timer_enabled = enabled_result.stdout.strip() or 'unknown'

    return build_snapshot(
        nft_document=nft_document,
        nft_error=nft_error,
        service=service,
        timer_active=timer_active,
        timer_enabled=timer_enabled,
    )


def write_snapshot(snapshot: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + '.tmp')
    temporary.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    os.chmod(temporary, 0o644)
    temporary.replace(output)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--nft', type=Path, default=DEFAULT_NFT)
    parser.add_argument('--systemctl', type=Path, default=DEFAULT_SYSTEMCTL)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    snapshot = collect_live_state(nft_path=args.nft, systemctl_path=args.systemctl)
    write_snapshot(snapshot, args.output)
    print(json.dumps({
        'ok': True,
        'output': str(args.output),
        'state': snapshot['enforcement']['state'],
        'verified': snapshot['enforcement']['verified'],
        'traffic_controls_changed': False,
    }))


if __name__ == '__main__':
    main()
