#!/usr/bin/env python3
"""Publish sanitized aggregate evidence for the live Edge1 nftables ruleset."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Callable, Sequence

DEFAULT_OUTPUT = Path('/var/lib/bigbird-networking/nftables/live-state.json')
DEFAULT_NFT = Path('/usr/sbin/nft')
DEFAULT_SYSTEMCTL = Path('/usr/bin/systemctl')
SERVICE_NAME = 'nftables.service'
CONTRACT = 'wwcx.nftables-aggregate-live-state.v1'

CommandRunner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]

FAMILIES = ('ip', 'ip6', 'inet', 'arp', 'bridge', 'netdev')
HOOKS = ('prerouting', 'input', 'forward', 'output', 'postrouting', 'ingress', 'egress')
POLICIES = ('accept', 'drop')
VERDICTS = ('accept', 'drop', 'reject', 'continue', 'return', 'jump', 'goto', 'queue')
OBJECT_TYPES = (
    'table', 'chain', 'rule', 'set', 'map', 'counter', 'quota', 'limit',
    'flowtable', 'ct helper', 'ct timeout', 'ct expectation', 'synproxy',
)


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).isoformat()


def safe_int(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def default_runner(args: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )


def parse_systemctl_show(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in text.splitlines():
        key, separator, value = raw.partition('=')
        if separator and key:
            values[key] = value
    return values


def blank_counts(keys: Sequence[str], include_other: bool = True) -> dict[str, int]:
    result = {key: 0 for key in keys}
    if include_other:
        result['other'] = 0
    return result


def add_bucket(counts: dict[str, int], value: Any, allowed: Sequence[str]) -> None:
    token = str(value or '').lower()
    counts[token if token in allowed else 'other'] += 1


def walk_expression(value: Any, verdicts: dict[str, int], counters: dict[str, int]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in VERDICTS:
                verdicts[key] += 1
            if key == 'counter' and isinstance(child, dict):
                counters['statement_count'] += 1
                counters['packets'] += safe_int(child.get('packets'))
                counters['bytes'] += safe_int(child.get('bytes'))
            walk_expression(child, verdicts, counters)
    elif isinstance(value, list):
        for child in value:
            walk_expression(child, verdicts, counters)


def element_count(value: Any) -> int:
    return len(value) if isinstance(value, list) else 0


def parse_ruleset(document: dict[str, Any]) -> dict[str, Any]:
    records = document.get('nftables') if isinstance(document.get('nftables'), list) else []
    object_counts = {key: 0 for key in OBJECT_TYPES}
    object_counts['other'] = 0
    family_counts = blank_counts(FAMILIES)
    hook_counts = blank_counts(HOOKS)
    policy_counts = blank_counts(POLICIES)
    verdict_counts = blank_counts(VERDICTS, include_other=False)
    counter_totals = {'statement_count': 0, 'packets': 0, 'bytes': 0}
    set_element_count = 0
    map_element_count = 0
    base_chain_count = 0
    rules_with_counters = 0
    rules_with_verdicts = 0

    for record in records:
        if not isinstance(record, dict):
            continue
        recognized = False
        for object_type in OBJECT_TYPES:
            value = record.get(object_type)
            if not isinstance(value, dict):
                continue
            recognized = True
            object_counts[object_type] += 1
            if object_type in {'table', 'chain', 'rule', 'set', 'map', 'flowtable'}:
                add_bucket(family_counts, value.get('family'), FAMILIES)
            if object_type == 'chain' and value.get('hook') is not None:
                base_chain_count += 1
                add_bucket(hook_counts, value.get('hook'), HOOKS)
                add_bucket(policy_counts, value.get('policy'), POLICIES)
            elif object_type == 'rule':
                before_counter = counter_totals['statement_count']
                before_verdict = sum(verdict_counts.values())
                walk_expression(value.get('expr'), verdict_counts, counter_totals)
                if counter_totals['statement_count'] > before_counter:
                    rules_with_counters += 1
                if sum(verdict_counts.values()) > before_verdict:
                    rules_with_verdicts += 1
            elif object_type == 'set':
                set_element_count += element_count(value.get('elem'))
            elif object_type == 'map':
                map_element_count += element_count(value.get('elem'))
        if not recognized and 'metainfo' not in record:
            object_counts['other'] += 1

    return {
        'objects': object_counts,
        'families': family_counts,
        'base_chains': {
            'count': base_chain_count,
            'hooks': hook_counts,
            'policies': policy_counts,
        },
        'rules': {
            'with_counters': rules_with_counters,
            'with_verdicts': rules_with_verdicts,
            'verdicts': verdict_counts,
        },
        'elements': {
            'set_count': set_element_count,
            'map_count': map_element_count,
        },
        'counter_totals': counter_totals,
    }


def build_snapshot(
    ruleset_document: dict[str, Any] | None,
    ruleset_error: str | None,
    service: dict[str, str],
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    current = now or utc_now()
    aggregates = parse_ruleset(ruleset_document or {})
    table_count = safe_int(aggregates['objects'].get('table'))
    chain_count = safe_int(aggregates['objects'].get('chain'))
    rule_count = safe_int(aggregates['objects'].get('rule'))

    if ruleset_error == 'nft command is not installed':
        state = 'not_installed'
        observed = False
        detail = 'The nft command is not installed or executable.'
    elif ruleset_error:
        state = 'unavailable'
        observed = False
        detail = 'The live nftables ruleset could not be inspected.'
    elif table_count == 0:
        state = 'empty'
        observed = True
        detail = 'The nftables query succeeded and returned no tables.'
    elif chain_count == 0 or rule_count == 0:
        state = 'partial'
        observed = True
        detail = 'The nftables ruleset is present, but its aggregate topology is incomplete.'
    else:
        state = 'ruleset_observed'
        observed = True
        detail = 'The live nftables ruleset topology and counters were observed in sanitized aggregate form.'

    service_loaded = service.get('LoadState') == 'loaded'
    service_success = service.get('Result') in {'success', ''} and service.get('ExecMainStatus') in {'0', ''}
    errors: list[str] = []
    if ruleset_error:
        errors.append(ruleset_error)
    if service and not service_loaded:
        errors.append('nftables service unit is not loaded')
    if service and not service_success:
        errors.append('nftables service result is not success')

    return {
        'schema_version': '1.0',
        'contract': CONTRACT,
        'generated_at': iso(current),
        'read_only': True,
        'traffic_controls_changed': False,
        'privacy': {
            'addresses_included': False,
            'interfaces_included': False,
            'table_names_included': False,
            'chain_names_included': False,
            'set_names_included': False,
            'set_elements_included': False,
            'map_elements_included': False,
            'rule_expressions_included': False,
            'rule_comments_included': False,
            'rule_handles_included': False,
            'full_ruleset_included': False,
            'raw_command_output_included': False,
            'credentials_included': False,
            'private_keys_included': False,
        },
        'service': {
            'name': SERVICE_NAME,
            'load_state': service.get('LoadState') or 'unknown',
            'active_state': service.get('ActiveState') or 'unknown',
            'sub_state': service.get('SubState') or 'unknown',
            'unit_file_state': service.get('UnitFileState') or 'unknown',
            'result': service.get('Result') or 'unknown',
            'exec_main_status': service.get('ExecMainStatus') or 'unknown',
            'loaded': service_loaded,
            'last_result_success': service_success,
        },
        'observation': {
            'state': state,
            'observed': observed,
            'enforcement_verified': False,
            'detail': detail,
        },
        'aggregates': aggregates,
        'errors': errors,
    }


def collect_live_state(
    nft_path: Path = DEFAULT_NFT,
    systemctl_path: Path = DEFAULT_SYSTEMCTL,
    runner: CommandRunner = default_runner,
) -> dict[str, Any]:
    nft_result = runner([str(nft_path), '-j', 'list', 'ruleset'])
    ruleset_document: dict[str, Any] | None = None
    ruleset_error: str | None = None
    if nft_result.returncode == 0:
        try:
            value = json.loads(nft_result.stdout)
            if not isinstance(value, dict):
                raise ValueError('not an object')
            ruleset_document = value
        except (json.JSONDecodeError, ValueError):
            ruleset_error = 'nft returned invalid JSON'
    elif nft_result.returncode == 127 or 'not found' in (nft_result.stderr or '').lower():
        ruleset_error = 'nft command is not installed'
    else:
        ruleset_error = 'nft ruleset query is unavailable'

    service_result = runner([
        str(systemctl_path), 'show', SERVICE_NAME,
        '--property=LoadState', '--property=ActiveState', '--property=SubState',
        '--property=UnitFileState', '--property=Result', '--property=ExecMainStatus',
    ])
    service = parse_systemctl_show(service_result.stdout) if service_result.returncode == 0 else {}
    return build_snapshot(ruleset_document, ruleset_error, service)


def write_snapshot(snapshot: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + '.tmp')
    temporary.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    os.chmod(temporary, 0o640)
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
        'state': snapshot['observation']['state'],
        'tables': snapshot['aggregates']['objects']['table'],
        'chains': snapshot['aggregates']['objects']['chain'],
        'rules': snapshot['aggregates']['objects']['rule'],
        'counter_packets': snapshot['aggregates']['counter_totals']['packets'],
        'counter_bytes': snapshot['aggregates']['counter_totals']['bytes'],
        'enforcement_verified': False,
        'traffic_controls_changed': False,
    }))


if __name__ == '__main__':
    main()
