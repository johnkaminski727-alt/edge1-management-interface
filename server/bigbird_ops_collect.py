#!/usr/bin/env python3
"""Source-controlled Project Big Bird operations collector for Edge1."""

import datetime as dt
import hashlib
import ipaddress
import json
import os
import re
import subprocess
from collections import deque
from pathlib import Path

try:
    from office_portability_bridge_summary import build_summary as build_office_portability_summary
except ImportError:
    build_office_portability_summary = None

OUT = Path('/var/lib/bigbird/operations-center')
SURICATA_SERVICE = os.environ.get('WWCX_SURICATA_SERVICE', 'wwcx-network-sensor-suricata.service')
EVE = Path(os.environ.get('WWCX_SURICATA_EVE', '/var/log/wwcx-network-sensor/suricata/eve.json'))
COLLECTOR_RELEASE = 'edge1-suricata-enrichment-r1'
SURICATA_SOURCE_RELEASE = 'edge1-suricata-sensor-consolidation-r1'
SURICATA_ALERT_SCHEMA = 'wwcx.suricata-source-alert.v1'


def run(args, timeout=20, limit=450000):
    try:
        p = subprocess.run(args, text=True, capture_output=True, timeout=timeout, check=False)
        return p.returncode == 0, p.stdout[-limit:], p.stderr[-20000:]
    except Exception as exc:
        return False, '', str(exc)


def clean(value):
    if not isinstance(value, str):
        return value
    value = re.sub(r'(?i)(private[-_ ]?key|preshared[-_ ]?key|password|secret|token)\s*[:=]\s*\S+', r'\1=[REDACTED]', value)
    return re.sub(r'(?i)\b[A-Za-z0-9+/]{48,}={0,2}\b', '[REDACTED-LONG-VALUE]', value)


def bounded_text(value, maximum=512):
    if value is None:
        return None
    text = clean(str(value)).strip()
    return text[:maximum] if text else None


def bounded_integer(value, minimum=0, maximum=None):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    if number < minimum or (maximum is not None and number > maximum):
        return None
    return number


def tail_lines(path, limit):
    with path.open('r', encoding='utf-8', errors='replace') as handle:
        return list(deque(handle, maxlen=limit))


def normalize_suricata_alert(event):
    """Return only allowlisted EVE alert fields; never return the raw event."""
    if not isinstance(event, dict) or event.get('event_type') != 'alert':
        return None
    alert = event.get('alert', {})
    if not isinstance(alert, dict):
        alert = {}
    return {
        'timestamp': bounded_text(event.get('timestamp'), 128),
        'signature': bounded_text(alert.get('signature')) or 'Unknown',
        'severity': bounded_integer(alert.get('severity'), 0, 255),
        'category': bounded_text(alert.get('category')),
        'action': bounded_text(alert.get('action'), 64),
        'source': bounded_text(event.get('src_ip'), 128),
        'destination': bounded_text(event.get('dest_ip'), 128),
        'source_port': bounded_integer(event.get('src_port'), 1, 65535),
        'destination_port': bounded_integer(event.get('dest_port'), 1, 65535),
        'protocol': bounded_text(event.get('proto'), 32),
        'application_protocol': bounded_text(event.get('app_proto'), 64),
        'signature_id': bounded_integer(alert.get('signature_id'), 0),
        'generator_id': bounded_integer(alert.get('gid'), 0),
        'revision': bounded_integer(alert.get('rev'), 0),
        'flow_id': bounded_integer(event.get('flow_id'), 0),
        'event_id': bounded_text(event.get('event_id'), 128),
    }


def service(name):
    ok, active, _ = run(['systemctl', 'is-active', name])
    _, enabled, _ = run(['systemctl', 'is-enabled', name])
    _, detail, _ = run(['systemctl', 'show', name, '--no-pager', '--property=ActiveState,SubState,UnitFileState,ExecMainStatus,StateChangeTimestamp'])
    props = {}
    for line in detail.splitlines():
        if '=' in line:
            key, value = line.split('=', 1)
            props[key] = value
    return {'name': name, 'active': active.strip() if ok else 'inactive', 'enabled': enabled.strip(), 'properties': props}


def expr_counter(expr):
    packets = bytes_count = 0
    for item in expr if isinstance(expr, list) else []:
        counter = item.get('counter') if isinstance(item, dict) else None
        if isinstance(counter, dict):
            packets += int(counter.get('packets', 0) or 0)
            bytes_count += int(counter.get('bytes', 0) or 0)
    return packets, bytes_count


def recent_firewall_events():
    ok, output, _ = run(['journalctl', '-k', '-n', '2500', '--no-pager', '--output=json'])
    if not ok:
        return []
    prefix = re.compile(r'BBFW\s+(INBOUND|FORWARD|OUTBOUND)\s+(POLICY|INVALID|BLOCKLIST)\s+')
    key_values = re.compile(r'\b([A-Z][A-Z0-9_]*)=([^\s]+)')
    events = []
    for line in output.splitlines():
        try:
            row = json.loads(line)
        except Exception:
            continue
        message = str(row.get('MESSAGE', ''))
        match = prefix.search(message)
        if not match:
            continue
        values = dict(key_values.findall(message))
        micros = int(row.get('__REALTIME_TIMESTAMP', 0) or 0)
        timestamp = dt.datetime.fromtimestamp(micros / 1000000, dt.timezone.utc).isoformat() if micros else ''
        events.append({'timestamp': timestamp, 'direction': match.group(1).lower(), 'reason': match.group(2).lower(), 'source': values.get('SRC', ''), 'destination': values.get('DST', ''), 'protocol': values.get('PROTO', ''), 'source_port': values.get('SPT', ''), 'destination_port': values.get('DPT', ''), 'input_interface': values.get('IN', ''), 'output_interface': values.get('OUT', '')})
    return events[-250:]


def firewall():
    ok, output, error = run(['nft', '-j', 'list', 'ruleset'])
    if not ok:
        return {'available': False, 'error': clean(error)}
    try:
        raw = json.loads(output)
    except Exception:
        return {'available': False, 'error': 'nft returned invalid JSON'}
    counts = {'tables': 0, 'chains': 0, 'rules': 0, 'sets': 0, 'maps': 0, 'counters': 0}
    rules = []
    policies = {}
    managed = {}
    for obj in raw.get('nftables', []):
        if 'table' in obj:
            counts['tables'] += 1
        if 'chain' in obj:
            counts['chains'] += 1
            chain = obj['chain']
            policies['/'.join(map(str, [chain.get('family', ''), chain.get('table', ''), chain.get('name', '')]))] = chain.get('policy', '')
        if 'rule' in obj:
            counts['rules'] += 1
            rule = obj['rule']
            expression = rule.get('expr', [])
            packets, bytes_count = expr_counter(expression)
            comment = clean(rule.get('comment', ''))
            if comment:
                managed[comment] = {'packets': packets, 'bytes': bytes_count}
            rules.append({'family': rule.get('family'), 'table': rule.get('table'), 'chain': rule.get('chain'), 'handle': rule.get('handle'), 'comment': comment, 'packets': packets, 'bytes': bytes_count, 'expr': expression})
        if 'set' in obj:
            counts['sets'] += 1
        if 'map' in obj:
            counts['maps'] += 1
        if 'counter' in obj:
            counts['counters'] += 1

    def total(*names):
        return {'packets': sum(int(managed.get(name, {}).get('packets', 0) or 0) for name in names), 'bytes': sum(int(managed.get(name, {}).get('bytes', 0) or 0) for name in names)}

    inbound = total('bigbird:blocked-inbound-v4', 'bigbird:blocked-inbound-v6', 'bigbird:blocked-input-invalid', 'bigbird:blocked-input-policy')
    forwarded = total('bigbird:blocked-forward-invalid', 'bigbird:blocked-forward-policy')
    outbound = total('bigbird:blocked-outbound-v4', 'bigbird:blocked-outbound-v6')
    activity = {'inbound': inbound, 'forwarded': forwarded, 'outbound': outbound, 'total': {'packets': inbound['packets'] + forwarded['packets'] + outbound['packets'], 'bytes': inbound['bytes'] + forwarded['bytes'] + outbound['bytes']}, 'recent_blocked_events': recent_firewall_events(), 'definition': {'inbound': 'Rejected before Edge1 services', 'forwarded': 'Rejected while traversing Edge1', 'outbound': 'Rejected by managed outbound block lists'}}
    canonical = json.dumps(raw, sort_keys=True, separators=(',', ':')).encode()
    return {'available': True, 'counts': counts, 'sha256': hashlib.sha256(canonical).hexdigest(), 'chain_policies': policies, 'managed_counters': managed, 'activity': activity, 'rules': rules[:1500]}


def recent_dns_queries():
    ok, output, _ = run(['journalctl', '-u', 'unbound.service', '-n', '3500', '--no-pager', '--output=json'])
    if not ok:
        return []
    pattern = re.compile(r'\bquery:\s+(\S+)\s+(\S+)\s+([A-Z0-9]+)\s+([A-Z0-9]+)\b')
    result = []
    for line in output.splitlines():
        try:
            row = json.loads(line)
        except Exception:
            continue
        match = pattern.search(str(row.get('MESSAGE', '')))
        if not match:
            continue
        client, name, record_type, record_class = match.groups()
        name = name.rstrip('.')
        try:
            ipaddress.ip_address(client)
        except ValueError:
            continue
        if len(name) > 253:
            continue
        micros = int(row.get('__REALTIME_TIMESTAMP', 0) or 0)
        timestamp = dt.datetime.fromtimestamp(micros / 1000000, dt.timezone.utc).isoformat() if micros else ''
        result.append({'timestamp': timestamp, 'client': client, 'query': name, 'type': record_type, 'class': record_class})
    return result[-250:]


def unbound():
    ok, output, error = run(['unbound-control', 'stats_noreset'])
    statistics = {}
    if ok:
        for line in output.splitlines():
            if '=' in line:
                key, value = line.split('=', 1)
                statistics[key] = value
    valid, _, configuration_error = run(['unbound-checkconf'])
    queries = recent_dns_queries()
    return {'available': ok, 'statistics': statistics, 'configuration_valid': valid, 'error': clean(error or configuration_error) if not ok or not valid else '', 'recent_queries': queries, 'recent_query_count': len(queries), 'recent_query_limit': 250}


def wireguard():
    ok, output, error = run(['wg', 'show', 'all', 'dump'])
    if not ok:
        return {'available': False, 'error': clean(error), 'interfaces': [], 'peers': []}
    interfaces = []
    peers = []
    for line in output.splitlines():
        fields = line.split('\t')
        if len(fields) == 5:
            interfaces.append({'interface': fields[0], 'public_key_fingerprint': hashlib.sha256(fields[2].encode()).hexdigest()[:16], 'listen_port': fields[3], 'fwmark': fields[4]})
        elif len(fields) >= 9:
            peers.append({'interface': fields[0], 'peer_fingerprint': hashlib.sha256(fields[1].encode()).hexdigest()[:16], 'allowed_ips': fields[4], 'latest_handshake': fields[5], 'rx_bytes': fields[6], 'tx_bytes': fields[7], 'persistent_keepalive': fields[8]})
    return {'available': True, 'interfaces': interfaces, 'peers': peers}


def suricata(eve_path=None):
    eve = Path(eve_path) if eve_path is not None else EVE
    recent = []
    counts = {}
    if eve.is_file():
        try:
            for line in tail_lines(eve, 5000):
                try:
                    event = json.loads(line)
                except Exception:
                    continue
                normalized = normalize_suricata_alert(event)
                if normalized is None:
                    continue
                signature = normalized['signature']
                counts[signature] = counts.get(signature, 0) + 1
                recent.append(normalized)
        except Exception:
            pass
    return {
        'available': eve.is_file(),
        'service': SURICATA_SERVICE,
        'source_path': str(eve),
        'source_release': SURICATA_SOURCE_RELEASE,
        'alert_schema': SURICATA_ALERT_SCHEMA,
        'counts': dict(sorted(counts.items(), key=lambda item: -item[1])[:50]),
        'recent_alerts': recent[-100:],
        'privacy': {
            'packet_payloads_included': False,
            'raw_events_included': False,
            'credentials_included': False,
            'private_keys_included': False,
        },
    }


def automation():
    ok, output, error = run(['systemctl', 'list-timers', '--all', '--no-pager', '--output=json'])
    timers = []
    if ok:
        try:
            timers = json.loads(output)
        except Exception:
            timers = [{'error': 'systemd JSON output unavailable'}]
    cron = []
    sources = [Path('/etc/crontab')]
    directory = Path('/etc/cron.d')
    if directory.is_dir():
        sources += list(directory.glob('*'))
    for source in sources:
        if not source.is_file():
            continue
        try:
            cron.append({'source': str(source), 'entries': [clean(line) for line in source.read_text(errors='replace').splitlines() if line.strip() and not line.lstrip().startswith('#')][:200]})
        except Exception:
            pass
    return {'timers': timers, 'timers_error': clean(error) if not ok else '', 'cron': cron}


def logs():
    result = {}
    for unit in ['bigbird.service', 'bigbird-worker.service', 'nftables.service', 'unbound.service', 'wg-quick@wg0.service', SURICATA_SERVICE, 'ssh.service']:
        _, output, _ = run(['journalctl', '-u', unit, '-n', '100', '--no-pager', '--output=short-iso'], timeout=15)
        result[unit] = [clean(line) for line in output.splitlines()][-100:]
    return result


def watched_paths():
    result = []
    for name in ['/etc/nftables.conf', '/etc/unbound', '/etc/wireguard', '/etc/suricata', '/etc/systemd/system', '/etc/cron.d', '/opt/bigbird/current', '/etc/bigbird/current']:
        path = Path(name)
        try:
            stat = path.stat()
            result.append({'path': name, 'mtime_utc': dt.datetime.fromtimestamp(stat.st_mtime, dt.timezone.utc).isoformat(), 'mode': oct(stat.st_mode & 0o777), 'kind': 'directory' if path.is_dir() else 'file'})
        except Exception:
            pass
    return result


def office_portability():
    if build_office_portability_summary is None:
        return {
            'ava_office': {'available': False, 'mode': 'read-only', 'execution_enabled': False},
            'number_portability': {'available': False, 'mode': 'read-only', 'submission_authorized': False, 'cutover_authorized': False},
            'privacy': {
                'record_level_content_included': False,
                'telephone_numbers_included': False,
                'transcripts_or_audio_included': False,
                'document_references_included': False,
                'credentials_included': False,
            },
        }
    try:
        return build_office_portability_summary()
    except Exception:
        return {
            'ava_office': {'available': False, 'mode': 'read-only', 'execution_enabled': False, 'error': 'summary_unavailable'},
            'number_portability': {'available': False, 'mode': 'read-only', 'submission_authorized': False, 'cutover_authorized': False, 'error': 'summary_unavailable'},
            'privacy': {
                'record_level_content_included': False,
                'telephone_numbers_included': False,
                'transcripts_or_audio_included': False,
                'document_references_included': False,
                'credentials_included': False,
            },
        }


def build_snapshot():
    now = dt.datetime.now(dt.timezone.utc)
    units = ['bigbird.service', 'bigbird-worker.service', 'nftables.service', 'unbound.service', 'wg-quick@wg0.service', SURICATA_SERVICE, 'bigbird-observatory.timer', 'bigbird-capture-prune.timer', 'bigbird-firewall-observability.service', 'bigbird-ops-push.timer']
    office = office_portability()
    return {
        'format': 'project-big-bird-operations-center-v1',
        'project_version': '4.0.5',
        'extension_release': 'v4.0.7-observability-r1',
        'collector_release': COLLECTOR_RELEASE,
        'generated_at': now.isoformat(),
        'generated_unix': int(now.timestamp()),
        'read_only': True,
        'provisioning_locked': True,
        'authoritative_dns_editing_locked': True,
        'host': {'node': 'Edge1', 'hostname_fingerprint': hashlib.sha256(os.uname().nodename.encode()).hexdigest()[:16], 'kernel': os.uname().release},
        'services': [service(unit) for unit in units],
        'firewall': firewall(),
        'dns_cache': unbound(),
        'vpn_devices': wireguard(),
        'security': suricata(),
        'automation': automation(),
        'logs': logs(),
        'changes_audit': {'watched_paths': watched_paths(), 'notice': 'Observability counters and empty managed block sets are installed. No web mutation endpoint exists.'},
        'settings': {'snapshot_interval_seconds': 120, 'browser_refresh_seconds': 45, 'stale_after_seconds': 360, 'write_controls': 'locked', 'firewall_control_release': 'guarded-control-pending', 'dyn_api_release': '4.0.6-reserved'},
        'ava_office': office['ava_office'],
        'number_portability': office['number_portability'],
        'office_services_privacy': office['privacy'],
    }


def write_snapshot(snapshot, output_dir=None):
    directory = Path(output_dir) if output_dir is not None else OUT
    directory.mkdir(parents=True, exist_ok=True)
    os.chmod(directory, 0o700)
    encoded = json.dumps(snapshot, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode() + b'\n'
    if len(encoded) > 4500000:
        raise SystemExit('snapshot exceeds safe receiver budget')
    temporary = directory / 'latest.json.tmp'
    temporary.write_bytes(encoded)
    os.chmod(temporary, 0o600)
    os.replace(temporary, directory / 'latest.json')
    return len(encoded)


def main():
    snapshot = build_snapshot()
    size = write_snapshot(snapshot)
    print(json.dumps({'ok': True, 'generated_at': snapshot['generated_at'], 'collector_release': snapshot['collector_release'], 'bytes': size}))


if __name__ == '__main__':
    main()
