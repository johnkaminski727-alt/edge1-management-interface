#!/usr/bin/env python3
"""Publish sanitized read-only Fail2ban service and jail health evidence."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Callable, Sequence

DEFAULT_OUTPUT = Path('/var/lib/bigbird-security/fail2ban/live-state.json')
DEFAULT_CLIENT = Path('/usr/bin/fail2ban-client')
DEFAULT_SYSTEMCTL = Path('/usr/bin/systemctl')
SERVICE_NAME = 'fail2ban.service'
SCHEMA_VERSION = 'wwcx.fail2ban-live-state.v1'
MAX_JAILS = 64
JAIL_NAME = re.compile(r'^[A-Za-z0-9_.-]{1,64}$')

CommandRunner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).isoformat()


def default_runner(args: Sequence[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            list(args),
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return subprocess.CompletedProcess(list(args), 127, '', str(exc))


def parse_systemctl_show(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in text.splitlines():
        key, separator, value = raw.partition('=')
        if separator and key:
            values[key] = value
    return values


def safe_count(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def sanitize_jail_name(value: str) -> str | None:
    candidate = value.strip()
    return candidate if JAIL_NAME.fullmatch(candidate) else None


def parse_status(text: str) -> tuple[int, list[str]]:
    declared = 0
    count_match = re.search(r'Number of jail:\s*(\d+)', text, flags=re.IGNORECASE)
    if count_match:
        declared = safe_count(count_match.group(1))

    list_match = re.search(r'Jail list:\s*([^\r\n]*)', text, flags=re.IGNORECASE)
    jails: list[str] = []
    if list_match:
        for raw in list_match.group(1).split(','):
            name = sanitize_jail_name(raw)
            if name and name not in jails:
                jails.append(name)
            if len(jails) >= MAX_JAILS:
                break
    return declared, jails


def parse_jail_status(text: str) -> dict[str, int]:
    result: dict[str, int] = {}
    labels = {
        'currently_failed': 'Currently failed',
        'total_failed': 'Total failed',
        'currently_banned': 'Currently banned',
        'total_banned': 'Total banned',
    }
    for key, label in labels.items():
        match = re.search(rf'{re.escape(label)}:\s*(\d+)', text, flags=re.IGNORECASE)
        result[key] = safe_count(match.group(1)) if match else 0
    return result


def build_snapshot(
    service: dict[str, str],
    client_returncode: int | None,
    declared_jail_count: int,
    jail_names: list[str],
    jail_records: dict[str, dict[str, int]],
    jail_errors: list[str] | None = None,
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    current = now or utc_now()
    errors = list(jail_errors or [])
    load_state = service.get('LoadState') or 'unknown'
    active_state = service.get('ActiveState') or 'unknown'
    sub_state = service.get('SubState') or 'unknown'
    result = service.get('Result') or 'unknown'
    exec_status = service.get('ExecMainStatus') or 'unknown'
    unit_file_state = service.get('UnitFileState') or 'unknown'

    installed = load_state not in {'not-found', 'error'}
    service_active = active_state == 'active'
    client_reachable = client_returncode == 0
    sanitized_names = [name for name in jail_names if sanitize_jail_name(name)][:MAX_JAILS]
    complete_jails = all(name in jail_records for name in sanitized_names)
    count_consistent = declared_jail_count == len(sanitized_names)

    if not installed or client_returncode == 127:
        state = 'not_installed'
        detail = 'Fail2ban is not installed or its local client is unavailable.'
        health_observed = False
    elif not service_active:
        state = 'inactive'
        detail = 'The Fail2ban service is installed but is not active.'
        health_observed = True
    elif not client_reachable:
        state = 'unavailable'
        detail = 'The Fail2ban service is active, but the local control socket could not be queried.'
        health_observed = False
    elif not complete_jails or not count_consistent or errors:
        state = 'partial'
        detail = 'Fail2ban service state and some jail counters were observed, but the complete jail-health contract was not available.'
        health_observed = True
    else:
        state = 'active_observed'
        detail = 'Fail2ban service state and sanitized aggregate counters for all reported jails were observed.'
        health_observed = True

    if installed and service_active and result not in {'success', 'unknown'}:
        errors.append('service result is not success')
    if client_reachable and not count_consistent:
        errors.append('declared jail count does not match sanitized jail list')

    jails: list[dict[str, Any]] = []
    aggregate = {
        'currently_failed': 0,
        'total_failed': 0,
        'currently_banned': 0,
        'total_banned': 0,
    }
    for name in sorted(sanitized_names):
        counts = jail_records.get(name)
        if not isinstance(counts, dict):
            continue
        record = {'name': name}
        for key in aggregate:
            value = safe_count(counts.get(key))
            record[key] = value
            aggregate[key] += value
        jails.append(record)

    return {
        'schema_version': '1.0',
        'contract': SCHEMA_VERSION,
        'generated_at': iso(current),
        'read_only': True,
        'traffic_controls_changed': False,
        'privacy': {
            'banned_addresses_included': False,
            'log_paths_included': False,
            'raw_client_output_included': False,
            'commands_included': False,
            'credentials_included': False,
            'private_keys_included': False,
        },
        'service': {
            'name': SERVICE_NAME,
            'load_state': load_state,
            'active_state': active_state,
            'sub_state': sub_state,
            'result': result,
            'exec_main_status': exec_status,
            'unit_file_state': unit_file_state,
            'installed': installed,
            'active': service_active,
        },
        'client': {
            'socket_reachable': client_reachable,
        },
        'jails': {
            'declared_count': safe_count(declared_jail_count),
            'observed_count': len(jails),
            'records': jails,
            'aggregate': aggregate,
        },
        'observation': {
            'state': state,
            'jail_health_observed': health_observed,
            'enforcement_verified': False,
            'detail': detail,
        },
        'errors': sorted(set(errors)),
    }


def collect_live_state(
    client_path: Path = DEFAULT_CLIENT,
    systemctl_path: Path = DEFAULT_SYSTEMCTL,
    runner: CommandRunner = default_runner,
) -> dict[str, Any]:
    service_result = runner([
        str(systemctl_path), 'show', SERVICE_NAME,
        '--property=LoadState', '--property=ActiveState', '--property=SubState',
        '--property=Result', '--property=ExecMainStatus', '--property=UnitFileState',
    ])
    service = parse_systemctl_show(service_result.stdout) if service_result.returncode == 0 else {}

    if service.get('LoadState') == 'not-found':
        return build_snapshot(service, 127, 0, [], {}, ['service unit is not installed'])

    root_status = runner([str(client_path), 'status'])
    declared_count = 0
    jail_names: list[str] = []
    jail_records: dict[str, dict[str, int]] = {}
    jail_errors: list[str] = []

    if root_status.returncode == 0:
        declared_count, jail_names = parse_status(root_status.stdout)
        for name in jail_names:
            status = runner([str(client_path), 'status', name])
            if status.returncode != 0:
                jail_errors.append(f'jail status unavailable: {name}')
                continue
            jail_records[name] = parse_jail_status(status.stdout)
    elif root_status.returncode != 127:
        jail_errors.append('Fail2ban local control socket query failed')

    return build_snapshot(
        service=service,
        client_returncode=root_status.returncode,
        declared_jail_count=declared_count,
        jail_names=jail_names,
        jail_records=jail_records,
        jail_errors=jail_errors,
    )


def write_snapshot(snapshot: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + '.tmp')
    temporary.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    os.chmod(temporary, 0o640)
    temporary.replace(output)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--client', type=Path, default=DEFAULT_CLIENT)
    parser.add_argument('--systemctl', type=Path, default=DEFAULT_SYSTEMCTL)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    snapshot = collect_live_state(client_path=args.client, systemctl_path=args.systemctl)
    write_snapshot(snapshot, args.output)
    print(json.dumps({
        'ok': True,
        'output': str(args.output),
        'state': snapshot['observation']['state'],
        'jail_count': snapshot['jails']['observed_count'],
        'currently_banned': snapshot['jails']['aggregate']['currently_banned'],
        'enforcement_verified': False,
        'traffic_controls_changed': False,
    }))


if __name__ == '__main__':
    main()
