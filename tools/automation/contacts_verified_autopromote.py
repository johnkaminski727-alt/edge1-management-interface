#!/usr/bin/env python3
from __future__ import annotations

import argparse
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
CONTACTS = Path('/var/lib/edge1-phone-intelligence/phone-intelligence.sqlite')
POLICY_VERSION = 'v3'
CREDENTIALS_DIRECTORY = os.environ.get('CREDENTIALS_DIRECTORY', '').strip()
SECRET = Path(CREDENTIALS_DIRECTORY) / 'operations_api_secret' if CREDENTIALS_DIRECTORY else Path('/etc/edge1-operations-api.secret')
TRUSTED_VERIFICATION = {'verified', 'document_sourced'}
BLOCKED_PERSON = {
    'info','client','west','support','service','team','billing','renewals','renewal',
    'reminder','ebill','catch','newsletter','surveys','confirmation','notices',
    'careerservices','noreply','no','reply','marketing','promotions','offers',
    'notifications','notification','sales','office','admin','accounts','claims',
}
GENERIC_DOMAIN_LABELS = {
    'www','mail','email','account','accounts','members','payments','insideapple',
    'business','intl','nab2b','estudante','m','app','apps','portal','secure',
}
BAD_ORG_PHRASES = {
    'is on the way','thanks for','thank you','confirmation','automatic reply',
    'your account','has been updated','unable to','welcome to','newsletter',
}


def _norm(value: str) -> str:
    return re.sub(r'[^a-z0-9]+', '', str(value or '').casefold())


def _evidence(row, db):
    email = str(row['sender_email'] or '').strip().casefold()
    if '@' not in email:
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
    return email, evidence, hashlib.sha256(
        json.dumps(evidence, sort_keys=True, separators=(',', ':')).encode()
    ).hexdigest()


def _person_candidate(row, evidence_info):
    email, _evidence_json, evidence_sha = evidence_info
    local = email.split('@', 1)[0].split('+', 1)[0]
    match = re.fullmatch(r"([a-z][a-z'-]{1,40})\.([a-z][a-z'-]{1,40})", local)
    if not match or any(token in BLOCKED_PERSON for token in match.groups()):
        return None
    return {
        'discovery_id': int(row['id']),
        'entity_type': 'person',
        'canonical_name': ' '.join(token.capitalize() for token in match.groups()),
        'sender_email': email,
        'message_count': int(row['message_count'] or 0),
        'evidence_sha256': evidence_sha,
        'promotion_basis': 'verified_named_mailbox',
    }


def _domain_stems(domain: str) -> list[str]:
    labels = [part for part in str(domain or '').casefold().split('.') if part]
    stems = []
    for label in labels:
        normalized = _norm(label)
        if label in GENERIC_DOMAIN_LABELS or len(normalized) < 5:
            continue
        stems.append(normalized)
    return list(dict.fromkeys(stems))


def _existing_org_candidate(row, evidence_info, organizations):
    email, _evidence_json, evidence_sha = evidence_info
    stems = _domain_stems(row['sender_domain'])
    matches = []
    for org in organizations:
        if str(org['verification_status'] or '') not in TRUSTED_VERIFICATION:
            continue
        org_norm = _norm(org['canonical_name'])
        if any(stem in org_norm or org_norm == stem for stem in stems):
            matches.append(org)
    unique = {int(item['id']): item for item in matches}
    if len(unique) != 1:
        return None
    org = next(iter(unique.values()))
    return {
        'discovery_id': int(row['id']),
        'entity_type': 'organization',
        'canonical_name': str(org['canonical_name']),
        'existing_entity_id': int(org['id']),
        'sender_email': email,
        'message_count': int(row['message_count'] or 0),
        'evidence_sha256': evidence_sha,
        'promotion_basis': 'verified_existing_organization_domain_match',
    }


def _proposed_org_candidate(row, evidence_info, state_db):
    email, evidence, evidence_sha = evidence_info
    name = ' '.join(str(row['proposed_entity_name'] or '').split())
    if not name or int(row['message_count'] or 0) < 3:
        return None
    if len(name) > 100 or not (2 <= len(name.split()) <= 10):
        return None
    lowered = name.casefold()
    if any(phrase in lowered for phrase in BAD_ORG_PHRASES):
        return None
    subjects = [str(value or '') for value in evidence.get('subjects', [])]
    documented = any(lowered in subject.casefold() for subject in subjects)
    if not documented:
        message_ids = [
            str(value).strip() for value in evidence.get('message_ids', [])
            if isinstance(value, str) and str(value).strip()
        ]
        if message_ids:
            marks = ','.join('?' for _ in message_ids)
            documented_count = state_db.execute(
                f"SELECT COUNT(DISTINCT e.message_id) FROM mail_contact_extractions e "
                f"JOIN mail_contact_candidates c ON c.extraction_id=e.id "
                f"WHERE e.message_id IN ({marks}) AND e.security_state='released' "
                f"AND lower(COALESCE(c.context,'')) LIKE ?",
                (*message_ids, '%' + lowered + '%'),
            ).fetchone()[0]
            documented = int(documented_count or 0) >= 2
    if not documented:
        return None
    return {
        'discovery_id': int(row['id']),
        'entity_type': 'organization',
        'canonical_name': name,
        'sender_email': email,
        'message_count': int(row['message_count'] or 0),
        'evidence_sha256': evidence_sha,
        'promotion_basis': 'verified_documented_organization_name',
    }


def eligible(row, state_db, organizations):
    evidence_info = _evidence(row, state_db)
    if not evidence_info:
        return None
    person = _person_candidate(row, evidence_info)
    if person:
        return person
    existing_org = _existing_org_candidate(row, evidence_info, organizations)
    if existing_org:
        return existing_org
    return _proposed_org_candidate(row, evidence_info, state_db)


def collect(limit: int):
    if not STATE.is_file() or not CONTACTS.is_file():
        raise SystemExit('contacts databases are unavailable')
    state = sqlite3.connect(f'file:{STATE}?mode=ro', uri=True)
    state.row_factory = sqlite3.Row
    contacts = sqlite3.connect(f'file:{CONTACTS}?mode=ro', uri=True)
    contacts.row_factory = sqlite3.Row
    try:
        organizations = contacts.execute(
            "SELECT id,canonical_name,verification_status FROM contact_entities "
            "WHERE entity_type='organization' AND lifecycle_status='active'"
        ).fetchall()
        candidates = []
        for row in state.execute(
            "SELECT id,sender_email,sender_domain,proposed_entity_name,message_count,evidence_json "
            "FROM contact_discovery_queue WHERE status='pending' ORDER BY message_count DESC,id ASC"
        ):
            candidate = eligible(row, state, organizations)
            if candidate:
                candidates.append(candidate)
            if len(candidates) >= limit:
                break
        return candidates
    finally:
        contacts.close()
        state.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--limit', type=int, default=25)
    args = parser.parse_args()
    limit = max(1, min(int(args.limit), 100))
    candidates = collect(limit)
    result = {'eligible': len(candidates), 'promoted': 0, 'deferred': 0, 'items': []}
    if args.dry_run:
        result['items'] = candidates
        print(json.dumps(result, sort_keys=True))
        return

    client = Edge1OperationsClient(secret_path=SECRET, timeout_seconds=30)
    for item in candidates:
        material = (
            f"{POLICY_VERSION}|{item['discovery_id']}|{item['entity_type']}|"
            f"{item['canonical_name']}|{item['sender_email']}|{item['evidence_sha256']}"
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
