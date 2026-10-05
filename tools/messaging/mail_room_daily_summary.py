#!/usr/bin/env python3
"""Aggregate-only Edge1 daily activity; source stores are opened read-only."""
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import argparse
import hashlib
import json
import os
import pwd
import sqlite3

TZ = ZoneInfo('America/Regina')
# Exact local commissioning message, not a subject-based guess about customer mail.
COMMISSIONING_HASHES = {'bf875f6bfec25adcfc6cad3886b42eba54dc24f4bbb2f4d36a4538722eb8d223'}


def bounds(day):
    start = datetime.combine(day, time.min, TZ)
    return start.astimezone(timezone.utc), (start + timedelta(days=1)).astimezone(timezone.utc)


def stamp(value):
    if isinstance(value, (int, float)): return datetime.fromtimestamp(value, timezone.utc)
    result = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    return result.replace(tzinfo=timezone.utc) if result.tzinfo is None else result.astimezone(timezone.utc)


def audit(path, start, end, events):
    counts = {e: 0 for e in events}; people = set(); bad = 0; seen = set()
    if not path.is_file(): return counts, None, 'unavailable'
    with path.open() as f:
        for line in f:
            try:
                row = json.loads(line)
                occurred = stamp(row.get('timestamp', row.get('occurred_at')))
                event = row.get('event_type', row.get('event'))
                if not start <= occurred < end or event not in counts: continue
                event_id = row.get('event_id')
                if event_id and event_id in seen: continue
                if event_id: seen.add(event_id)
                counts[event] += 1
                if event == 'login_succeeded' and row.get('actor_subject'): people.add(row['actor_subject'])
            except (ValueError, TypeError, OverflowError): bad += 1
    return counts, len(people), 'partial' if bad else 'available'


def db_counts(path, queries, start, end):
    if not path.is_file(): return {k: None for k in queries}, 'unavailable'
    result = {}
    try:
        with sqlite3.connect('file:' + str(path) + '?mode=ro', uri=True) as db:
            for key, query in queries.items():
                result[key] = db.execute(query, (start.isoformat(), end.isoformat())).fetchone()[0]
        return result, 'available'
    except (sqlite3.Error, OSError): return {k: None for k in queries}, 'unavailable'


def build(day, paths, now=None):
    now = now or datetime.now(timezone.utc); start, end = bounds(day)
    auth, users, auth_state = audit(paths['auth'], start, end, ['login_succeeded','login_failed','logout'])
    mail, _, mail_state = audit(paths['outbound'], start, end, ['outbound_message_submitted','outbound_message_prepared_api'])
    counts = {'successful_logins': auth['login_succeeded'] if auth_state != 'unavailable' else None, 'unique_login_users': users, 'failed_logins': auth['login_failed'] if auth_state != 'unavailable' else None, 'logouts': auth['logout'] if auth_state != 'unavailable' else None, 'messages_sent': mail['outbound_message_submitted'] if mail_state != 'unavailable' else None, 'drafts_prepared': mail['outbound_message_prepared_api'] if mail_state != 'unavailable' else None}
    received = None; tests = None; receive_state = 'unavailable'
    if paths['mail'].is_file():
        try:
            with sqlite3.connect('file:' + str(paths['mail']) + '?mode=ro', uri=True) as db:
                rows = db.execute("SELECT message_id FROM correspondence WHERE source_authoritative=1 AND source_scope IN ('local_native','production_native') AND direction='inbound' AND julianday(occurred_at)>=julianday(?) AND julianday(occurred_at)<julianday(?)", (start.isoformat(), end.isoformat())).fetchall()
            tests = sum(hashlib.sha256(r[0].encode()).hexdigest() in COMMISSIONING_HASHES for r in rows); received = len(rows)-tests; receive_state = 'available'
        except (sqlite3.Error, OSError): pass
    counts.update(messages_received=received, commissioning_messages_received=tests)
    contact, contact_state = db_counts(paths['contacts'], {k: 'SELECT count(*) FROM '+table+' WHERE julianday(created_at)>=julianday(?) AND julianday(created_at)<julianday(?)' for k, table in [('new_contacts','contact_entities'),('new_contact_points','contact_points'),('new_contact_relationships','contact_relationships')]}, start, end)
    counts.update(contact)
    return {'contract': 'wwcx.daily-activity.v1', 'date': day.isoformat(), 'timezone': 'America/Regina', 'generated_at': now.isoformat(), 'period_start_utc': start.isoformat(), 'period_end_utc': end.isoformat(), 'complete_day': now >= end, 'counts': counts, 'sources': {'authentication': auth_state,'outbound_audit': mail_state,'received_mail': receive_state,'contacts': contact_state}, 'notes': ['Logins count successful Edge1 portal session issuance, not page refreshes or SSH sessions.', 'Sent means provider submission was recorded; delivery or recipient reading is not implied.', 'Received counts authoritative intake by its recorded event time; the known commissioning canary is separate.', 'Preparation counts include recorded commissioning tests; preparation never means sent.', 'Contacts count newly created entities; imports are included. Contact points and relationships are separate.', 'Totals cover retained records. Missing or malformed sources are marked unavailable/partial.'], 'content_included': False}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=Path('/var/lib/wwcx-mail-room-reports'));args=parser.parse_args()
    paths={'auth':Path('/var/lib/wwcx-edge1-ops/audit/security-auth.jsonl'),'outbound':Path('/var/lib/wwcx-outbound-mail/audit.jsonl'),'mail':Path('/var/lib/wwcx-mail-room/correspondence.sqlite3'),'contacts':Path('/var/lib/edge1-phone-intelligence/phone-intelligence.sqlite')}
    os.umask(0o077); args.output.mkdir(mode=0o750,exist_ok=True); group=pwd.getpwnam('wwcx-mail-gateway').pw_gid;os.chown(args.output,0,group);args.output.chmod(0o750)
    today=datetime.now(TZ).date()
    for day in [today-timedelta(days=1),today]:
        report=build(day,paths);target=args.output/(day.isoformat()+'.json');temp=target.with_suffix('.tmp');temp.write_text(json.dumps(report,indent=2)+'\n');os.chown(temp,0,group);temp.chmod(0o640);temp.replace(target)
    print(json.dumps({'generated_dates':[(today-timedelta(days=1)).isoformat(),today.isoformat()],'timezone':'America/Regina','content_included':False}))

if __name__=='__main__':main()
