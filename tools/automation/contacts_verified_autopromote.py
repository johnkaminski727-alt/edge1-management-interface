#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.edge1_operations_client import Edge1OperationsClient, OperationsClientError

STATE = Path('/var/lib/edge1-contacts-maintenance/maintenance.sqlite')
POLICY_VERSION = 'v2'
CREDENTIALS_DIRECTORY = os.environ.get('CREDENTIALS_DIRECTORY', '').strip()
SECRET = (Path(CREDENTIALS_DIRECTORY) / 'operations_api_secret') if CREDENTIALS_DIRECTORY else Path('/etc/edge1-operations-api.secret')
BLOCKED = {
    'info','client','west','support','service','team','billing','renewals','renewal',
    'reminder','ebill','catch','newsletter','surveys','confirmation','notices',
    'careerservices','noreply','no','reply','marketing','promotions','offers',
    'notifications','notification','sales','office','admin','accounts','claims',
}


def eligible(row, db):
    email = str(row['sender_email'] or '').strip().casefold()
    if '@' not in email:
        return None
    local = email.split('@', 1)[0].split('+', 1)[0]
    match = re.fullmatch(r"([a-z][a-z'-]{1,40})\.([a-z][a-z'-]{1,40})", local)
    if not match or any(token in BLOCKED for token in match.groups()):
        return None
    try:
        evidence = json.loads(row['evidence_json'] or '{}')
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(evidence, dict):
        return None
    message_ids = list(dict.fromkeys(
        value.strip() for value in evidence.get('message_ids', [])
        if isinstance(value, str) and value.strip()
    ))
    if len(message_ids) < 2:
        return None
    marks = ','.join('?' for _ in message_ids)
    released = db.execute(
        f"SELECT COUNT(DISTINCT message_id) FROM mail_contact_extractions "
        f"WHERE message_id IN ({marks}) AND security_state='released'",
        message_ids,
    ).fetchone()[0]
    if int(released or 0) < 2:
        return None
    coordinates = [item for item in evidence.get('coordinates', []) if isinstance(item, dict)]
    sender_supported = any(
        item.get('type') == 'email'
        and str(item.get('value') or '').strip().casefold() == email
        and str(item.get('confidence') or '') in {'high','confirmed','verified','document_sourced'}
        for item in coordinates
    )
    corroborated = any(item.get('type') in {'phone','postal_address'} for item in coordinates)
    if not sender_supported or not corroborated:
        return None
    return {
        'discovery_id': int(row['id']),
        'entity_type': 'person',
        'canonical_name': ' '.join(token.capitalize() for token in match.groups()),
        'sender_email': email,
        'message_count': int(row['message_count'] or 0),
        'evidence_sha256': hashlib.sha256(
            json.dumps(evidence, sort_keys=True, separators=(',', ':')).encode()
        ).hexdigest(),
    }


def main():
    if not STATE.is_file():
        raise SystemExit('maintenance database missing')
    db = sqlite3.connect(f'file:{STATE}?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    candidates = []
    try:
        for row in db.execute(
            "SELECT id,sender_email,message_count,evidence_json FROM contact_discovery_queue "
            "WHERE status='pending' ORDER BY message_count DESC,id ASC"
        ):
            candidate = eligible(row, db)
            if candidate:
                candidates.append(candidate)
            if len(candidates) >= 25:
                break
    finally:
        db.close()

    client = Edge1OperationsClient(secret_path=SECRET, timeout_seconds=30)
    result = {'eligible': len(candidates), 'promoted': 0, 'deferred': 0, 'items': []}
    for item in candidates:
        material = (
            f"{POLICY_VERSION}|{item['discovery_id']}|{item['canonical_name']}|"
            f"{item['sender_email']}|{item['evidence_sha256']}"
        )
        key = 'verified-discovery-' + hashlib.sha256(material.encode()).hexdigest()[:32]
        try:
            response = client.run(
                'contacts.discovery.promote',
                'contacts-maintenance-bot',
                parameters={
                    'discovery_id': item['discovery_id'],
                    'entity_type': item['entity_type'],
                    'canonical_name': item['canonical_name'],
                    'idempotency_key': key,
                },
            )
        except OperationsClientError as exc:
            result['deferred'] += 1
            result['items'].append({**item, 'status': 'deferred', 'reason': str(exc)})
            continue
        if response.status == 'succeeded':
            result['promoted'] += 1
            result['items'].append({
                **item, 'status': 'promoted', 'event_id': response.event_id,
                'entity_id': (response.result or {}).get('entity_id'),
            })
        else:
            result['deferred'] += 1
            result['items'].append({
                **item, 'status': 'deferred', 'event_id': response.event_id,
                'reason': response.message,
            })
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
