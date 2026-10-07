#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
if __package__:
    from tools.unified_contacts.source_reconciler import reconcile as reconcile_sources
else:
    from source_reconciler import reconcile as reconcile_sources

SCHEMA = '''
CREATE TABLE IF NOT EXISTS maintenance_runs(
 id INTEGER PRIMARY KEY AUTOINCREMENT, started_at TEXT NOT NULL, finished_at TEXT,
 source_sha256 TEXT, source_sha256_after TEXT, status TEXT NOT NULL, summary_json TEXT
);
CREATE TABLE IF NOT EXISTS maintenance_findings(
 id INTEGER PRIMARY KEY AUTOINCREMENT, fingerprint TEXT NOT NULL UNIQUE,
 finding_type TEXT NOT NULL, severity TEXT NOT NULL, action_level TEXT NOT NULL DEFAULT 'REVIEW_REQUIRED',
 entity_id INTEGER, contact_point_id INTEGER, title TEXT NOT NULL, detail TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'open', first_seen_at TEXT NOT NULL,
 last_seen_at TEXT NOT NULL, occurrences INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS enrichment_queue(
 id INTEGER PRIMARY KEY AUTOINCREMENT, fingerprint TEXT NOT NULL UNIQUE,
 entity_id INTEGER NOT NULL, task_type TEXT NOT NULL, rationale TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS candidate_changes(
 id INTEGER PRIMARY KEY AUTOINCREMENT, fingerprint TEXT NOT NULL UNIQUE,
 action_level TEXT NOT NULL, entity_id INTEGER, contact_point_id INTEGER,
 target_table TEXT NOT NULL, target_field TEXT NOT NULL,
 current_value TEXT, proposed_value TEXT, rationale TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS identity_resolution_queue(
 id INTEGER PRIMARY KEY AUTOINCREMENT, fingerprint TEXT NOT NULL UNIQUE,
 contact_point_id INTEGER NOT NULL, resolution_kind TEXT NOT NULL,
 normalized_value TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
 rationale TEXT NOT NULL, matched_entity_id INTEGER, proposed_entity_name TEXT,
 confidence TEXT, evidence_json TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_identity_resolution_status
ON identity_resolution_queue(status,resolution_kind);
CREATE TABLE IF NOT EXISTS remediation_actions(
 id INTEGER PRIMARY KEY AUTOINCREMENT, run_id INTEGER,
 action_level TEXT NOT NULL, action_type TEXT NOT NULL,
 target_table TEXT NOT NULL, target_id INTEGER NOT NULL, target_field TEXT NOT NULL,
 before_value TEXT, after_value TEXT, rationale TEXT NOT NULL,
 backup_path TEXT, source_sha256_before TEXT, source_sha256_after TEXT,
 verification_status TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_findings_status ON maintenance_findings(status, finding_type);
CREATE INDEX IF NOT EXISTS idx_enrichment_status ON enrichment_queue(status, task_type);
CREATE INDEX IF NOT EXISTS idx_candidate_status ON candidate_changes(status, action_level);
CREATE INDEX IF NOT EXISTS idx_remediation_run ON remediation_actions(run_id, action_level);
CREATE TABLE IF NOT EXISTS mail_contact_extractions(
 id INTEGER PRIMARY KEY AUTOINCREMENT, fingerprint TEXT NOT NULL UNIQUE,
 message_id TEXT NOT NULL, message_sha256 TEXT NOT NULL, occurred_at TEXT,
 sender TEXT, subject TEXT, security_state TEXT NOT NULL, reviewed INTEGER NOT NULL DEFAULT 0,
 extracted_at TEXT NOT NULL, attachment_count INTEGER NOT NULL DEFAULT 0,
 candidate_count INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'staged'
);
CREATE TABLE IF NOT EXISTS mail_contact_candidates(
 id INTEGER PRIMARY KEY AUTOINCREMENT, fingerprint TEXT NOT NULL UNIQUE,
 extraction_id INTEGER NOT NULL REFERENCES mail_contact_extractions(id) ON DELETE CASCADE,
 candidate_type TEXT NOT NULL, normalized_value TEXT NOT NULL, display_value TEXT NOT NULL,
 confidence TEXT NOT NULL, source_kind TEXT NOT NULL, source_reference TEXT NOT NULL,
 context TEXT, attachment_sha256 TEXT, status TEXT NOT NULL DEFAULT 'pending',
 matched_entity_id INTEGER, matched_contact_point_id INTEGER, created_at TEXT NOT NULL,
 UNIQUE(extraction_id,candidate_type,normalized_value,source_reference)
);
CREATE INDEX IF NOT EXISTS idx_mail_contact_candidate_status ON mail_contact_candidates(status,candidate_type);
CREATE TABLE IF NOT EXISTS contact_discovery_queue(
 id INTEGER PRIMARY KEY AUTOINCREMENT, fingerprint TEXT NOT NULL UNIQUE,
 sender_email TEXT NOT NULL, sender_domain TEXT NOT NULL, proposed_entity_name TEXT,
 message_count INTEGER NOT NULL, evidence_json TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'pending', matched_entity_id INTEGER,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_contact_discovery_status
ON contact_discovery_queue(status,message_count);
CREATE TABLE IF NOT EXISTS relationship_suggestion_queue(
 id INTEGER PRIMARY KEY AUTOINCREMENT, fingerprint TEXT NOT NULL UNIQUE,
 discovery_id INTEGER NOT NULL, proposed_person_name TEXT NOT NULL,
 sender_email TEXT NOT NULL, organization_entity_id INTEGER NOT NULL,
 relationship_type TEXT NOT NULL DEFAULT 'works_for', confidence TEXT NOT NULL,
 rationale TEXT NOT NULL, evidence_json TEXT,
 status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_relationship_suggestion_status
ON relationship_suggestion_queue(status,relationship_type);
'''


def utcnow():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def norm_name(value):
    return re.sub(r'[^a-z0-9]+', '', (value or '').casefold())


def fp(*parts):
    return hashlib.sha256('|'.join('' if p is None else str(p) for p in parts).encode()).hexdigest()


def _ensure_column(connection, table, definition):
    name = definition.split()[0]
    columns = {r[1] for r in connection.execute(f'PRAGMA table_info({table})')}
    if name not in columns:
        connection.execute(f'ALTER TABLE {table} ADD COLUMN {definition}')


def open_source(path, writable=False):
    if writable:
        connection = sqlite3.connect(path)
    else:
        connection = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA foreign_keys=ON')
    return connection


def open_state(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMA)
    _ensure_column(connection, 'maintenance_runs', 'source_sha256_after TEXT')
    _ensure_column(connection, 'maintenance_findings', "action_level TEXT NOT NULL DEFAULT 'REVIEW_REQUIRED'")
    return connection


def _table_exists(connection, name):
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone() is not None


def _column_exists(connection, table, column):
    if not _table_exists(connection, table):
        return False
    return any(row[1] == column for row in connection.execute(f'PRAGMA table_info({table})'))


def source_sha(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def finding(dst, kind, severity, title, detail, entity=None, point=None, action_level='REVIEW_REQUIRED'):
    now = utcnow()
    key = fp(kind, entity, point, title, detail)
    dst.execute('''
        INSERT INTO maintenance_findings(
            fingerprint,finding_type,severity,action_level,entity_id,contact_point_id,
            title,detail,first_seen_at,last_seen_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(fingerprint) DO UPDATE SET
            last_seen_at=excluded.last_seen_at,
            occurrences=maintenance_findings.occurrences+1,
            action_level=excluded.action_level,
            status=CASE WHEN maintenance_findings.status IN ('resolved','checking') THEN 'open' ELSE maintenance_findings.status END
    ''', (key, kind, severity, action_level, entity, point, title, detail, now, now))


def enrich(dst, entity, task, rationale):
    now = utcnow()
    key = fp(entity, task)
    dst.execute('''
        INSERT INTO enrichment_queue(fingerprint,entity_id,task_type,rationale,created_at,updated_at)
        VALUES(?,?,?,?,?,?)
        ON CONFLICT(fingerprint) DO UPDATE SET rationale=excluded.rationale,updated_at=excluded.updated_at,
            status=CASE WHEN enrichment_queue.status IN ('resolved','checking') THEN 'pending' ELSE enrichment_queue.status END
    ''', (key, entity, task, rationale, now, now))


def candidate(dst, action_level, target_table, target_id, target_field, current, proposed, rationale, entity=None, point=None):
    now = utcnow()
    key = fp(action_level, target_table, target_id, target_field, current, proposed, rationale)
    dst.execute('''
        INSERT INTO candidate_changes(
            fingerprint,action_level,entity_id,contact_point_id,target_table,target_field,
            current_value,proposed_value,rationale,created_at,updated_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(fingerprint) DO UPDATE SET updated_at=excluded.updated_at,
            status=CASE WHEN candidate_changes.status IN ('superseded','checking') THEN 'pending' ELSE candidate_changes.status END
    ''', (key, action_level, entity, point, target_table, target_field, current, proposed, rationale, now, now))


def identity_resolution(dst, point_id, resolution_kind, normalized_value, rationale, confidence=None, evidence=None):
    now = utcnow()
    key = fp(point_id, resolution_kind, normalized_value)
    evidence_json = json.dumps(evidence, sort_keys=True) if isinstance(evidence, dict) else None
    dst.execute('''
        INSERT INTO identity_resolution_queue(
            fingerprint,contact_point_id,resolution_kind,normalized_value,status,rationale,
            confidence,evidence_json,created_at,updated_at
        ) VALUES(?,?,?,?, 'pending', ?, ?, ?, ?, ?)
        ON CONFLICT(fingerprint) DO UPDATE SET
            rationale=excluded.rationale,
            confidence=COALESCE(excluded.confidence,identity_resolution_queue.confidence),
            evidence_json=COALESCE(excluded.evidence_json,identity_resolution_queue.evidence_json),
            updated_at=excluded.updated_at,
            status=CASE WHEN identity_resolution_queue.status IN ('resolved','superseded','checking') THEN 'pending' ELSE identity_resolution_queue.status END
    ''', (key, point_id, resolution_kind, normalized_value, rationale, confidence, evidence_json, now, now))


def collect_safe_fixes(src):
    fixes = []
    for row in src.execute('''
        SELECT id, canonical_name, display_name FROM contact_entities
        WHERE lifecycle_status='active' AND canonical_name IS NOT NULL AND TRIM(canonical_name)<>''
          AND (display_name IS NULL OR TRIM(display_name)='')
    '''):
        fixes.append({
            'action_type': 'fill_missing_display_name', 'target_table': 'contact_entities',
            'target_id': row['id'], 'target_field': 'display_name', 'before': row['display_name'],
            'after': row['canonical_name'], 'rationale': 'Display name was empty; canonical name is the existing authoritative identity label.'
        })
    for row in src.execute('''
        SELECT id, normalized_value, display_value FROM contact_points
        WHERE lifecycle_status='active' AND normalized_value IS NOT NULL AND TRIM(normalized_value)<>''
          AND (display_value IS NULL OR TRIM(display_value)='')
    '''):
        fixes.append({
            'action_type': 'fill_missing_display_value', 'target_table': 'contact_points',
            'target_id': row['id'], 'target_field': 'display_value', 'before': row['display_value'],
            'after': row['normalized_value'], 'rationale': 'Display value was empty; the existing normalized contact value is safe to use as a display fallback.'
        })
    for row in src.execute('''
        SELECT DISTINCT cp.id,cp.lifecycle_status
        FROM contact_points cp
        JOIN contact_assertions ca ON ca.contact_point_id=cp.id
        JOIN contact_entities e ON e.id=ca.entity_id
        WHERE cp.lifecycle_status='unknown'
          AND e.lifecycle_status='active'
          AND ca.confidence IN ('confirmed','verified','document_sourced')
          AND NOT EXISTS(
              SELECT 1 FROM contact_assertions ca2
              JOIN contact_entities e2 ON e2.id=ca2.entity_id
              WHERE ca2.contact_point_id=cp.id
                AND e2.lifecycle_status='active'
                AND ca2.confidence NOT IN ('confirmed','verified','document_sourced')
          )
    '''):
        fixes.append({
            'action_type': 'activate_strongly_asserted_contact_point', 'target_table': 'contact_points',
            'target_id': row['id'], 'target_field': 'lifecycle_status', 'before': row['lifecycle_status'],
            'after': 'active', 'rationale': 'The contact point was lifecycle=unknown but every active-entity assertion is independently confirmed or document-sourced.'
        })
    return fixes


def apply_safe_fixes(src, source_path, dst, run_id, backup_dir):
    fixes = collect_safe_fixes(src)
    if not fixes:
        return {'planned': 0, 'applied': 0, 'backup': None}

    before_sha = source_sha(source_path)
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup_path = backup_dir / f'phone-intelligence-before-autofix-{stamp}-run{run_id}.sqlite'
    shutil.copy2(source_path, backup_path)
    if source_sha(backup_path) != before_sha:
        backup_path.unlink(missing_ok=True)
        raise RuntimeError('pre-remediation backup hash verification failed')

    allowed = {
        ('contact_entities', 'display_name'),
        ('contact_points', 'display_value'),
        ('contact_points', 'lifecycle_status'),
    }
    applied = []
    try:
        src.execute('BEGIN IMMEDIATE')
        for fix in fixes:
            if (fix['target_table'], fix['target_field']) not in allowed:
                raise RuntimeError('AUTO-FIX attempted outside field allowlist')
            query = f"UPDATE {fix['target_table']} SET {fix['target_field']}=? WHERE id=? AND {fix['target_field']} IS ?"
            cursor = src.execute(query, (fix['after'], fix['target_id'], fix['before']))
            if cursor.rowcount != 1:
                raise RuntimeError(f"AUTO-FIX concurrency check failed for {fix['target_table']} id={fix['target_id']}")
            verify = src.execute(f"SELECT {fix['target_field']} FROM {fix['target_table']} WHERE id=?", (fix['target_id'],)).fetchone()
            if verify is None or verify[0] != fix['after']:
                raise RuntimeError('AUTO-FIX verification failed before commit')
            applied.append(fix)
        src.commit()
    except Exception:
        src.rollback()
        raise

    after_sha = source_sha(source_path)
    for fix in applied:
        verify = src.execute(f"SELECT {fix['target_field']} FROM {fix['target_table']} WHERE id=?", (fix['target_id'],)).fetchone()
        status = 'verified' if verify is not None and verify[0] == fix['after'] else 'verification_failed'
        dst.execute('''
            INSERT INTO remediation_actions(
                run_id,action_level,action_type,target_table,target_id,target_field,before_value,after_value,
                rationale,backup_path,source_sha256_before,source_sha256_after,verification_status,created_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (run_id, 'AUTO_FIX', fix['action_type'], fix['target_table'], fix['target_id'], fix['target_field'],
              fix['before'], fix['after'], fix['rationale'], str(backup_path), before_sha, after_sha, status, utcnow()))
        if status != 'verified':
            raise RuntimeError('AUTO-FIX post-commit verification failed; backup retained for rollback')
    return {'planned': len(fixes), 'applied': len(applied), 'backup': str(backup_path), 'source_sha256_after': after_sha}


def plausible_mail_phone_candidate(raw, context=''):
    raw=str(raw or '').strip(); context=str(context or '')
    digits=re.sub(r'\D','',raw); low=context.casefold()
    pos=context.find(raw)
    before=(context[max(0,pos-60):pos] if pos >= 0 else context[:60]).casefold()
    phone_words=('phone','telephone','tel:','tel ','mobile','cell','fax','call','contact details','contact number')
    obvious_noise=('ip address','confirmation number','confirmation:','pin code','tracking_pixel','invoice number','security code','verification code','order number','reference number')
    if any(x in low for x in obvious_noise) and not any(x in before for x in phone_words):
        return False
    if re.fullmatch(r'\d{1,3}(?:\.\d{1,3}){3}', raw):
        return False
    if re.fullmatch(r'20\d{2}[-/.]\d{1,2}[-/.]\d{1,2}.*', raw):
        return False
    if raw.startswith('+'):
        return 8 <= len(digits) <= 15
    if '\n' in raw or '\r' in raw:
        return False
    labelled=any(x in before for x in phone_words)
    formatted=bool(re.search(r'[()\-\s]', raw))
    if len(digits)==10 and digits[0] in '23456789' and digits[3] in '23456789':
        return labelled or formatted
    if len(digits)==11 and digits.startswith('1') and digits[1] in '23456789' and digits[4] in '23456789':
        return labelled or formatted
    if labelled:
        return 7 <= len(digits) <= 15 and len(set(digits)) > 2
    return False


def mail_candidate_disposition(row):
    ctype=str(row['candidate_type'] or '')
    value=str(row['normalized_value'] or '').strip()
    display=str(row['display_value'] or value).strip()
    context=str(row['context'] or '')
    source_kind=str(row['source_kind'] or '')
    low=value.casefold()
    if ctype=='phone':
        return None if plausible_mail_phone_candidate(display,context) else 'rejected_noise'
    if ctype=='email':
        if '@' not in value:
            return 'rejected_noise'
        local,domain=low.rsplit('@',1)
        if len(local)<=1 and '*' in context:
            return 'rejected_noise'
        if '%' in local or domain=='gtempaccount.com':
            return 'informational_only'
        if domain=='property.booking.com' and re.match(r'^\d',local):
            return 'informational_only'
        system_locals=('noreply','no-reply','do-not-reply','donotreply','account-security-noreply','appleid')
        if source_kind=='message_header' and any(
            local==x
            or local.startswith(x+'+')
            or local.startswith(x+'.')
            or local.startswith(x+'-')
            for x in system_locals
        ):
            return 'informational_only'
        bulk_domains=('newsletter.','marketing.','mail.')
        generic_locals=('news','newsletter','marketing','promotions','offers','team')
        if source_kind=='message_header' and (
            any(domain.startswith(prefix) for prefix in bulk_domains)
            and local in generic_locals
        ):
            return 'informational_only'
        return None
    if ctype=='job_title':
        if 'http://' in low or 'https://' in low or '@' in value:
            return 'rejected_noise'
        words=value.split()
        if len(value)>80 or len(words)>9 or len(words)<2:
            return 'rejected_noise'
        if re.search(r'\d{3,}', value) or any(ch in value for ch in ('📞','☎','\\n')):
            return 'rejected_noise'
        generic_terms=(
            'support center','support team','customer support','technical support','help desk',
            'contact support','contact our','need help','toll-free support','support line',
            'support number','roadside support','life support','support package',
            'support channels','support regarding','feature updates','spinal alignment',
            'sleep positions','minor sprains','business directory','group owner or manager',
            'store owners','thank you for contacting','qualify for elite support',
            'threatens man','manager-kontos gesperrt','administratora danych osobowych',
        )
        if any(term in low for term in generic_terms):
            return 'informational_only'
        role_terms=(
            'director','manager','president','vice president','owner','founder','coordinator',
            'administrator','representative','officer','accountant','lawyer','counsel',
        )
        if not any(re.search(r'\b'+re.escape(term)+r'\b', low) for term in role_terms):
            return 'informational_only'
        if low.startswith(('-', '*')) or low.endswith((':', '?')):
            return 'informational_only'
        return None
    if ctype=='postal_address':
        compact=' '.join(value.split())
        compact_low=compact.casefold()
        if re.fullmatch(r'[ABCEGHJ-NPRSTVXY]\d[ABCEGHJ-NPRSTVWXYZ][ -]?\d[ABCEGHJ-NPRSTVWXYZ]\d',compact,re.I):
            return 'informational_only'
        if any(term in compact_low for term in ('phone/text/fax','phone / text / fax','telephone','fax:')):
            return 'rejected_noise'
        if re.match(r'^\+?\d[\d() .-]{6,}\s+[ABCEGHJ-NPRSTVXY]\d[ABCEGHJ-NPRSTVWXYZ][ -]?\d[ABCEGHJ-NPRSTVWXYZ]\d$', compact, re.I):
            return 'rejected_noise'
        return None

def suppress_low_value_mail_candidates(dst):
    disposition_by_id={}
    rows=dst.execute("""
        SELECT id,candidate_type,display_value,normalized_value,context,source_kind
        FROM mail_contact_candidates
        WHERE status IN ('pending','queued_review','bundled_review')
    """).fetchall()
    for row in rows:
        disposition=mail_candidate_disposition(row)
        if disposition:
            disposition_by_id[int(row['id'])]=disposition
    if not disposition_by_id:
        return {'rejected_noise':0,'informational_only':0}
    for disposition in ('rejected_noise','informational_only'):
        ids=[candidate_id for candidate_id,status in disposition_by_id.items() if status==disposition]
        if not ids:
            continue
        placeholders=','.join('?' for _ in ids)
        dst.execute(f"UPDATE mail_contact_candidates SET status=? WHERE id IN ({placeholders})",(disposition,*ids))
    affected=set(disposition_by_id)
    for row in dst.execute("SELECT id,proposed_value FROM candidate_changes WHERE target_table='mail_contact_candidates' AND status IN ('pending','checking')").fetchall():
        try: detail=json.loads(row['proposed_value'] or '{}')
        except (TypeError,json.JSONDecodeError): continue
        if isinstance(detail,dict) and int(detail.get('representative_candidate_id') or 0) in affected:
            dst.execute("UPDATE candidate_changes SET status='superseded',updated_at=? WHERE id=?",(utcnow(),row['id']))
    for row in dst.execute("SELECT id,detail FROM maintenance_findings WHERE finding_type='mail_contact_candidate' AND status IN ('open','checking')").fetchall():
        try: detail=json.loads(row['detail'] or '{}')
        except (TypeError,json.JSONDecodeError): continue
        if isinstance(detail,dict) and int(detail.get('representative_candidate_id') or 0) in affected:
            dst.execute("UPDATE maintenance_findings SET status='resolved',last_seen_at=? WHERE id=?",(utcnow(),row['id']))
    return {
        'rejected_noise':sum(1 for status in disposition_by_id.values() if status=='rejected_noise'),
        'informational_only':sum(1 for status in disposition_by_id.values() if status=='informational_only'),
    }


def _discovery_name_from_subjects(subjects):
    for subject in subjects:
        text=' '.join(str(subject or '').split())
        match=re.search(r'\bfrom\s+([A-Z][A-Za-z0-9& .\'’/-]{2,79})',text)
        if not match:
            continue
        value=match.group(1).strip(' .:-')
        value=re.split(r'\s+[|–—-]\s+',value,maxsplit=1)[0].strip()
        if 2 <= len(value.split()) <= 10 and len(value) <= 80:
            return value
    return None


def _resolve_mail_review_artifacts(dst, candidate_ids):
    affected={int(value) for value in candidate_ids}
    if not affected:
        return
    for row in dst.execute("SELECT id,proposed_value FROM candidate_changes WHERE target_table='mail_contact_candidates' AND status IN ('pending','checking')").fetchall():
        try: detail=json.loads(row['proposed_value'] or '{}')
        except (TypeError,json.JSONDecodeError): continue
        if isinstance(detail,dict) and int(detail.get('representative_candidate_id') or 0) in affected:
            dst.execute("UPDATE candidate_changes SET status='superseded',updated_at=? WHERE id=?",(utcnow(),row['id']))
    for row in dst.execute("SELECT id,detail FROM maintenance_findings WHERE finding_type='mail_contact_candidate' AND status IN ('open','checking')").fetchall():
        try: detail=json.loads(row['detail'] or '{}')
        except (TypeError,json.JSONDecodeError): continue
        if isinstance(detail,dict) and int(detail.get('representative_candidate_id') or 0) in affected:
            dst.execute("UPDATE maintenance_findings SET status='resolved',last_seen_at=? WHERE id=?",(utcnow(),row['id']))


def build_contact_discoveries(dst):
    now=utcnow(); created_or_refreshed=0; bundled_ids=[]
    senders=dst.execute("""
        SELECT c.normalized_value sender_email,COUNT(DISTINCT c.extraction_id) message_count
        FROM mail_contact_candidates c
        WHERE c.candidate_type='email'
          AND c.source_kind='message_header'
          AND c.source_reference='sender'
          AND c.status IN ('pending','queued_review','bundled_review')
        GROUP BY c.normalized_value
        HAVING COUNT(DISTINCT c.extraction_id)>=2
        ORDER BY message_count DESC,c.normalized_value
        LIMIT 1000
    """).fetchall()
    for sender in senders:
        email=str(sender['sender_email'] or '').casefold()
        if '@' not in email:
            continue
        extraction_rows=dst.execute("""
            SELECT DISTINCT c.extraction_id,e.message_id,e.subject,e.occurred_at
            FROM mail_contact_candidates c
            JOIN mail_contact_extractions e ON e.id=c.extraction_id
            WHERE c.candidate_type='email' AND c.normalized_value=?
              AND c.source_kind='message_header' AND c.source_reference='sender'
              AND c.status IN ('pending','queued_review','bundled_review')
            ORDER BY e.occurred_at DESC,c.extraction_id DESC
        """,(email,)).fetchall()
        extraction_ids=[int(r['extraction_id']) for r in extraction_rows]
        if not extraction_ids:
            continue
        placeholders=','.join('?' for _ in extraction_ids)
        raw_related=dst.execute(f"""
            SELECT id,candidate_type,normalized_value,display_value,confidence,source_kind,source_reference,context
            FROM mail_contact_candidates
            WHERE extraction_id IN ({placeholders})
              AND status IN ('pending','queued_review','bundled_review')
              AND candidate_type IN ('phone','postal_address','email')
            ORDER BY candidate_type,id
        """,extraction_ids).fetchall()
        related=[]
        seen_coordinates=set()
        for candidate_row in raw_related:
            candidate_type=str(candidate_row['candidate_type'] or '')
            candidate_value=str(candidate_row['normalized_value'] or '').casefold()
            if candidate_type=='email' and candidate_value != email:
                continue
            coordinate_key=(candidate_type,candidate_value)
            if coordinate_key in seen_coordinates:
                continue
            seen_coordinates.add(coordinate_key)
            related.append(candidate_row)
        corroborating=[r for r in related if not (r['candidate_type']=='email' and str(r['normalized_value']).casefold()==email)]
        strong=[r for r in corroborating if r['candidate_type'] in ('phone','postal_address')]
        if not strong:
            continue
        subjects=[r['subject'] for r in extraction_rows if r['subject']]
        proposed=_discovery_name_from_subjects(subjects)
        evidence={
            'message_ids':[r['message_id'] for r in extraction_rows[:20]],
            'subjects':subjects[:10],
            'coordinates':[
                {
                    'candidate_id':int(r['id']),
                    'type':r['candidate_type'],
                    'value':r['normalized_value'],
                    'display':r['display_value'],
                    'confidence':r['confidence'],
                    'source_kind':r['source_kind'],
                    'source_reference':r['source_reference'],
                }
                for r in related[:40]
            ],
        }
        domain=email.rsplit('@',1)[1]
        key=fp('contact_discovery',email)
        dst.execute("""
            INSERT INTO contact_discovery_queue(
                fingerprint,sender_email,sender_domain,proposed_entity_name,message_count,
                evidence_json,status,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,'pending',?,?)
            ON CONFLICT(fingerprint) DO UPDATE SET
                proposed_entity_name=COALESCE(excluded.proposed_entity_name,contact_discovery_queue.proposed_entity_name),
                message_count=excluded.message_count,evidence_json=excluded.evidence_json,
                updated_at=excluded.updated_at,
                status=CASE WHEN contact_discovery_queue.status IN ('resolved','superseded','checking') THEN 'pending' ELSE contact_discovery_queue.status END
        """,(key,email,domain,proposed,len(extraction_ids),json.dumps(evidence,sort_keys=True),now,now))
        ids=[int(r['id']) for r in raw_related]
        if ids:
            marks=','.join('?' for _ in ids)
            dst.execute(f"UPDATE mail_contact_candidates SET status='bundled_review' WHERE id IN ({marks})",ids)
            bundled_ids.extend(ids)
        created_or_refreshed+=1
    _resolve_mail_review_artifacts(dst,bundled_ids)
    return {'discoveries':created_or_refreshed,'bundled_candidates':len(set(bundled_ids))}


def build_relationship_suggestions(src, dst):
    now=utcnow(); refreshed=0
    generic_locals={'info','support','service','news','hello','team','billing','renewals','renewal','reminder','ebill','catch','newsletter','surveys','confirmation','notices','careerservices'}
    rows=dst.execute("""
        SELECT id,sender_email,sender_domain,proposed_entity_name,message_count,evidence_json
        FROM contact_discovery_queue WHERE status='pending'
    """).fetchall()
    for row in rows:
        email=str(row['sender_email'] or '').strip().casefold()
        if '@' not in email:
            continue
        local,domain=email.rsplit('@',1)
        local_root=re.split(r'[+]',local,maxsplit=1)[0]
        if local_root in generic_locals or local_root.startswith(('no_reply','noreply','do_not_reply','sc-noreply')):
            continue
        tokens=[token for token in re.split(r'[._-]+',local_root) if token and token.isalpha()]
        if len(tokens) < 2:
            continue
        person_name=' '.join(token.capitalize() for token in tokens[:5])
        stem=domain.split('.')[-2] if domain.count('.') >= 1 else domain
        stem_norm=norm_name(stem)
        if len(stem_norm) < 4:
            continue
        matches=[]
        for org in src.execute("SELECT id,canonical_name FROM contact_entities WHERE lifecycle_status='active' AND entity_type='organization'"):
            org_norm=norm_name(org['canonical_name'])
            if stem_norm and (stem_norm in org_norm or org_norm in stem_norm):
                matches.append(org)
        if len(matches) != 1:
            continue
        org=matches[0]
        key=fp('relationship_suggestion',row['id'],person_name,org['id'],'works_for')
        rationale=f"Sender domain {domain} uniquely aligns with existing organization {org['canonical_name']}; person-like mailbox {email} suggests a possible works_for relationship. Review identity before promotion."
        evidence=json.dumps({'discovery_id':row['id'],'sender_email':email,'sender_domain':domain,'message_count':row['message_count']},sort_keys=True)
        dst.execute("""
            INSERT INTO relationship_suggestion_queue(
                fingerprint,discovery_id,proposed_person_name,sender_email,organization_entity_id,
                relationship_type,confidence,rationale,evidence_json,status,created_at,updated_at
            ) VALUES(?,?,?,?,?,'works_for','probable',?,?, 'pending',?,?)
            ON CONFLICT(fingerprint) DO UPDATE SET
                rationale=excluded.rationale,evidence_json=excluded.evidence_json,updated_at=excluded.updated_at,
                status=CASE WHEN relationship_suggestion_queue.status IN ('resolved','superseded','checking') THEN 'pending' ELSE relationship_suggestion_queue.status END
        """,(key,row['id'],person_name,email,org['id'],rationale,evidence,now,now))
        refreshed+=1
    return {'relationship_suggestions':refreshed}


def process_mail_contact_candidates(src, dst):
    suppressed = suppress_low_value_mail_candidates(dst)
    discoveries = build_contact_discoveries(dst)
    relationships = build_relationship_suggestions(src, dst)
    groups = dst.execute("""
        SELECT MIN(c.id) AS representative_id,c.candidate_type,c.normalized_value,
               COUNT(*) AS evidence_count,MIN(e.message_id) AS example_message_id
        FROM mail_contact_candidates c
        JOIN mail_contact_extractions e ON e.id=c.extraction_id
        WHERE c.status IN ('pending','queued_review')
        GROUP BY c.candidate_type,c.normalized_value
        ORDER BY representative_id LIMIT 5000
    """).fetchall()
    stats = {'unique_seen': len(groups), 'observations_seen': 0, 'matched_existing': 0, 'queued_review': 0, 'ambiguous': 0, 'deferred_unanchored': 0, **suppressed, **discoveries, **relationships}
    point_map = {'email':'email','phone':'phone','domain':'domain','website':'website','postal_address':'postal_address'}
    for group in groups:
        ctype, value = group['candidate_type'], group['normalized_value']
        stats['observations_seen'] += int(group['evidence_count'])
        occurrences = dst.execute("""
            SELECT c.id,c.extraction_id,c.source_kind,c.source_reference,c.attachment_sha256,e.message_id,e.sender
            FROM mail_contact_candidates c JOIN mail_contact_extractions e ON e.id=c.extraction_id
            WHERE c.status IN ('pending','queued_review') AND c.candidate_type=? AND c.normalized_value=? ORDER BY c.id
        """, (ctype, value)).fetchall()
        anchor_entities=set()
        for item in occurrences:
            match=re.search(r'([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,63})', item['sender'] or '', re.I)
            if not match: continue
            owners=src.execute("""
                SELECT DISTINCT ca.entity_id FROM contact_points cp
                JOIN contact_assertions ca ON ca.contact_point_id=cp.id
                WHERE cp.lifecycle_status='active' AND cp.point_type='email' AND lower(cp.normalized_value)=lower(?)
            """, (match.group(1).lower(),)).fetchall()
            if len(owners)==1: anchor_entities.add(owners[0][0])
        entity=next(iter(anchor_entities)) if len(anchor_entities)==1 else None
        point_type=point_map.get(ctype)
        matches=src.execute("SELECT id FROM contact_points WHERE lifecycle_status='active' AND point_type=? AND lower(normalized_value)=lower(?) ORDER BY id",(point_type,value)).fetchall() if point_type else []
        ids=[r['id'] for r in occurrences]
        placeholders=','.join('?' for _ in ids)
        if len(matches)==1:
            point_id=matches[0][0]
            owners=src.execute("SELECT DISTINCT entity_id FROM contact_assertions WHERE contact_point_id=?",(point_id,)).fetchall()
            matched_entity=owners[0][0] if len(owners)==1 else entity
            dst.execute(f"UPDATE mail_contact_candidates SET status='matched_existing',matched_contact_point_id=?,matched_entity_id=? WHERE id IN ({placeholders})",(point_id,matched_entity,*ids))
            stats['matched_existing']+=1; continue
        if len(matches)>1 or len(anchor_entities)>1:
            finding(dst,'mail_contact_candidate_ambiguous','high','Mail-derived contact evidence is ambiguous',f"type={ctype}; value={value}; evidence_count={group['evidence_count']}; example_message={group['example_message_id']}",action_level='REVIEW_REQUIRED')
            dst.execute(f"UPDATE mail_contact_candidates SET status='ambiguous' WHERE id IN ({placeholders})",ids)
            stats['ambiguous']+=1; continue
        if ctype in {'domain','website'} and entity is None:
            dst.execute(f"UPDATE mail_contact_candidates SET status='deferred_unanchored' WHERE id IN ({placeholders})",ids)
            stats['deferred_unanchored']+=1; continue
        rep=occurrences[0]
        evidence=json.dumps({'representative_candidate_id':group['representative_id'],'type':ctype,'value':value,'evidence_count':group['evidence_count'],'example_message_id':group['example_message_id'],'source_kind':rep['source_kind'],'source_reference':rep['source_reference'],'attachment_sha256':rep['attachment_sha256']},sort_keys=True)
        level='AUTO_STAGE' if entity and ctype in point_map else 'REVIEW_REQUIRED'
        rationale='Aggregated evidence from security-released Mail Room messages; candidate-only until Contacts policy validates identity and ownership.'
        finding(dst,'mail_contact_candidate','low' if level=='AUTO_STAGE' else 'medium','Mail-derived contact candidate',evidence,entity=entity,action_level=level)
        candidate(dst,level,'mail_contact_candidates',group['representative_id'],'candidate_review',None,evidence,rationale,entity=entity)
        dst.execute(f"UPDATE mail_contact_candidates SET status='queued_review',matched_entity_id=? WHERE id IN ({placeholders})",(entity,*ids))
        stats['queued_review']+=1
    return stats


def suggested_owner_for_unassigned_email(src, value):
    value=str(value or '').strip().casefold()
    if '@' not in value:
        return None
    domain=value.rsplit('@',1)[1]
    rows=src.execute('''
        SELECT e.id,COUNT(*) n
        FROM contact_points cp
        JOIN contact_assertions ca ON ca.contact_point_id=cp.id
        JOIN contact_entities e ON e.id=ca.entity_id
        WHERE cp.lifecycle_status='active'
          AND cp.point_type='email'
          AND lower(cp.normalized_value) LIKE ?
          AND e.entity_type='organization'
          AND e.lifecycle_status='active'
        GROUP BY e.id
        ORDER BY n DESC,e.id
    ''', ('%@'+domain,)).fetchall()
    if not rows or int(rows[0]['n']) < 2:
        return None
    top=int(rows[0]['n'])
    second=int(rows[1]['n']) if len(rows)>1 else 0
    if second and top < second * 2:
        return None
    return int(rows[0]['id'])


def begin_reconciliation_cycle(dst):
    dst.execute("UPDATE maintenance_findings SET status='checking' WHERE status='open'")
    dst.execute("UPDATE enrichment_queue SET status='checking' WHERE status='pending'")
    dst.execute("UPDATE candidate_changes SET status='checking' WHERE status='pending'")
    dst.execute("UPDATE identity_resolution_queue SET status='checking' WHERE status='pending'")
    dst.execute("UPDATE contact_discovery_queue SET status='checking' WHERE status='pending'")
    dst.execute("UPDATE relationship_suggestion_queue SET status='checking' WHERE status='pending'")


def finish_reconciliation_cycle(dst):
    dst.execute("UPDATE maintenance_findings SET status='resolved' WHERE status='checking'")
    dst.execute("UPDATE enrichment_queue SET status='resolved' WHERE status='checking'")
    dst.execute("UPDATE candidate_changes SET status='superseded' WHERE status='checking'")
    dst.execute("UPDATE identity_resolution_queue SET status='superseded' WHERE status='checking'")
    dst.execute("UPDATE contact_discovery_queue SET status='superseded' WHERE status='checking'")
    dst.execute("UPDATE relationship_suggestion_queue SET status='superseded' WHERE status='checking'")


def run(src, dst):
    rows = src.execute("SELECT id,entity_type,canonical_name FROM contact_entities WHERE lifecycle_status='active'").fetchall()
    groups = {}
    for row in rows:
        groups.setdefault((row['entity_type'], norm_name(row['canonical_name'])), []).append(row)
    for (kind, key), records in groups.items():
        if key and len(records) > 1:
            ids = [r['id'] for r in records]
            detail = f"{kind} records share normalized name {records[0]['canonical_name']!r}; entity_ids={ids}"
            finding(dst, 'duplicate_entity', 'high', 'Possible duplicate contacts', detail, action_level='REVIEW_REQUIRED')
            candidate(dst, 'REVIEW_REQUIRED', 'contact_entities', ids[0], 'identity_merge', str(ids), None,
                      'Potential identity merge requires human approval because it may be destructive.')

    for row in src.execute('''
        SELECT cp.id,cp.point_type,cp.normalized_value,COUNT(DISTINCT ca.entity_id) n,
               GROUP_CONCAT(DISTINCT ca.entity_id) ids,
               SUM(CASE WHEN ca.confidence IN ('confirmed','verified','document_sourced') THEN 0 ELSE 1 END) weak
        FROM contact_points cp JOIN contact_assertions ca ON ca.contact_point_id=cp.id
        JOIN contact_entities e ON e.id=ca.entity_id
        WHERE cp.lifecycle_status='active' AND e.lifecycle_status='active'
        GROUP BY cp.id HAVING COUNT(DISTINCT ca.entity_id)>1
    '''):
        if int(row['weak'] or 0) == 0:
            continue
        detail = f"{row['point_type']} {row['normalized_value']} is asserted for entity_ids={row['ids']}"
        finding(dst, 'shared_contact_point', 'medium', 'Contact point has ambiguous shared ownership', detail,
                point=row['id'], action_level='REVIEW_REQUIRED')
        candidate(dst, 'REVIEW_REQUIRED', 'contact_assertions', row['id'], 'ownership', row['ids'], None,
                  'At least one shared ownership assertion is not strongly verified and requires review.', point=row['id'])

    for row in src.execute('''
        SELECT cp.id,cp.point_type,cp.normalized_value FROM contact_points cp
        WHERE cp.lifecycle_status='active' AND NOT EXISTS(
            SELECT 1 FROM contact_assertions ca WHERE ca.contact_point_id=cp.id
        )
    '''):
        suggested_entity = (
            suggested_owner_for_unassigned_email(src, row['normalized_value'])
            if row['point_type'] == 'email'
            else None
        )
        if suggested_entity:
            detail = (
                f"{row['point_type']} {row['normalized_value']} has no canonical entity; "
                f"same-domain organization mailbox history suggests entity_id={suggested_entity}"
            )
            rationale = (
                'The mailbox domain has a dominant established organization owner. Stage attachment to that existing organization; do not create a duplicate contact.'
            )
            proposed = str(suggested_entity)
        else:
            detail = f"{row['point_type']} {row['normalized_value']} has no canonical entity"
            rationale = 'Unassigned contact point needs evidence-based identity resolution before attachment.'
            proposed = None
        finding(dst, 'unassigned_contact_point', 'low', 'Unassigned contact point',
                detail, entity=suggested_entity, point=row['id'], action_level='AUTO_STAGE')
        candidate(dst, 'AUTO_STAGE', 'contact_assertions', row['id'], 'entity_id', None, proposed,
                  rationale, entity=suggested_entity, point=row['id'])
        if row['point_type'] in ('phone', 'fax'):
            identity_resolution(
                dst, row['id'], 'reverse_phone', row['normalized_value'],
                'Correlate this unassigned number against existing contacts and approved evidence. Public external lookup is limited to business, organization, and public service identities; private-person identity discovery from a phone number is not automatic.'
            )

    if _table_exists(src, 'phone_numbers') and _column_exists(src, 'contact_points', 'legacy_phone_number_id'):
        legacy_rows = src.execute('''
            SELECT cp.id,cp.normalized_value,cp.display_value,
                   COALESCE(pn.status,'') legacy_status,
                   COALESCE(pn.occurrence_count,0) occurrence_count
            FROM contact_points cp
            LEFT JOIN phone_numbers pn ON pn.id=cp.legacy_phone_number_id
            WHERE cp.point_type='phone'
              AND cp.lifecycle_status='unknown'
              AND NOT EXISTS(
                  SELECT 1 FROM contact_assertions ca
                  WHERE ca.contact_point_id=cp.id
              )
              AND COALESCE(pn.status,'unresolved')='unresolved'
            ORDER BY COALESCE(pn.occurrence_count,0) DESC,cp.id
            LIMIT 500
        ''').fetchall()
        for row in legacy_rows:
            identity_resolution(
                dst,
                row['id'],
                'reverse_phone',
                row['normalized_value'],
                'Legacy unresolved phone observed repeatedly; correlate against canonical contacts, messages, documents, registers, and approved public/business lookup sources before any activation or assignment.',
                confidence='observed',
                evidence={
                    'occurrence_count': int(row['occurrence_count'] or 0),
                    'legacy_status': row['legacy_status'] or 'unresolved',
                    'display_value': row['display_value'],
                },
            )

    for entity in rows:
        types = {x[0] for x in src.execute('''
            SELECT DISTINCT cp.point_type FROM contact_assertions ca
            JOIN contact_points cp ON cp.id=ca.contact_point_id
            WHERE ca.entity_id=? AND cp.lifecycle_status='active'
        ''', (entity['id'],))}
        if 'phone' not in types:
            enrich(dst, entity['id'], 'find_phone', 'No active phone is recorded.')
        if 'email' not in types:
            enrich(dst, entity['id'], 'find_email', 'No active email is recorded.')
        if entity['entity_type'] == 'organization' and not ({'domain', 'website'} & types):
            enrich(dst, entity['id'], 'find_web_presence', 'No domain or website is recorded.')
        if 'postal_address' not in types:
            enrich(dst, entity['id'], 'find_address', 'No postal address is recorded.')

    for row in src.execute("SELECT id,point_type,normalized_value FROM contact_points WHERE lifecycle_status='active'"):
        value = (row['normalized_value'] or '').strip()
        bad = False
        if row['point_type'] == 'email':
            bad = not bool(re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', value))
        elif row['point_type'] == 'domain':
            bad = not bool(re.fullmatch(r'(?=.{1,253}$)([A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}', value))
        elif row['point_type'] in ('phone', 'fax'):
            bad = len(re.sub(r'\D', '', value)) < 7
        if bad:
            finding(dst, 'validation_issue', 'medium', 'Contact point needs validation',
                    f"{row['point_type']} value {value!r} failed basic syntax validation",
                    point=row['id'], action_level='AUTO_STAGE')
            candidate(dst, 'AUTO_STAGE', 'contact_points', row['id'], 'normalized_value', value, None,
                      'Invalid syntax requires evidence-backed correction; never guess a replacement.', point=row['id'])

    mail_candidates = process_mail_contact_candidates(src, dst)
    return {
        'entities': len(rows),
        'open_findings': dst.execute("SELECT COUNT(*) FROM maintenance_findings WHERE status='open'").fetchone()[0],
        'pending_enrichment': dst.execute("SELECT COUNT(*) FROM enrichment_queue WHERE status='pending'").fetchone()[0],
        'pending_candidates': dst.execute("SELECT COUNT(*) FROM candidate_changes WHERE status='pending'").fetchone()[0],
        'mail_contact_candidates': mail_candidates,
    }


def process_source_reconciliation(dst, result):
    for item in result['results']:
        pid = item['provenance_id']
        status = item['status']
        if status in ('verified', 'declared'):
            continue
        if status == 'candidate':
            finding(dst, 'source_relocation_candidate', 'medium', 'Evidence source may have moved',
                    f"provenance_id={pid}; candidate_location={item['location']}", action_level='AUTO_STAGE')
            candidate(dst, 'AUTO_STAGE', 'provenance_source_locations', pid, 'location', None, item['location'],
                      'A unique filename match was found, but no strong hash evidence exists; verify before linking.')
        elif status == 'ambiguous':
            finding(dst, 'source_location_ambiguous', 'high', 'Evidence source location is ambiguous',
                    f"provenance_id={pid}; matches={item['location']}", action_level='REVIEW_REQUIRED')
            candidate(dst, 'REVIEW_REQUIRED', 'provenance_source_locations', pid, 'location', None, item['location'],
                      'Multiple or conflicting source matches require review before changing evidence location.')
        elif status == 'missing':
            finding(dst, 'source_missing', 'low', 'Evidence source is not currently locatable',
                    f"provenance_id={pid}; expected={item['location']}", action_level='AUTO_STAGE')


def create_verified_backup(source_path, backup_dir, run_id, label):
    before_sha = source_sha(source_path)
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup_path = backup_dir / f'phone-intelligence-before-{label}-{stamp}-run{run_id}.sqlite'
    shutil.copy2(source_path, backup_path)
    if source_sha(backup_path) != before_sha:
        backup_path.unlink(missing_ok=True)
        raise RuntimeError(f'{label} backup hash verification failed')
    return backup_path, before_sha


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', default='/var/lib/edge1-phone-intelligence/phone-intelligence.sqlite')
    parser.add_argument('--state', default='/var/lib/edge1-contacts-maintenance/maintenance.sqlite')
    parser.add_argument('--backup-dir', default='/var/lib/edge1-contacts-maintenance/backups')
    parser.add_argument('--source-root', action='append', dest='source_roots', help='approved root to search for moved evidence files')
    parser.add_argument('--apply-safe', action='store_true', help='apply allowlisted AUTO-FIX remediations')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()

    source_path = Path(args.source)
    state_path = Path(args.state)
    if not source_path.is_file():
        raise SystemExit('source database missing')

    before_sha = source_sha(source_path)
    with closing(open_source(source_path, writable=args.apply_safe)) as src, closing(open_state(state_path)) as dst:
        started = utcnow()
        cursor = dst.execute(
            "INSERT INTO maintenance_runs(started_at,source_sha256,status) VALUES(?,?,?)",
            (started, before_sha, 'running')
        )
        run_id = cursor.lastrowid
        try:
            remediation = {'planned': len(collect_safe_fixes(src)), 'applied': 0, 'backup': None}
            if args.apply_safe:
                remediation = apply_safe_fixes(src, source_path, dst, run_id, Path(args.backup_dir))
            roots = args.source_roots or ['/home/wwadmin', '/var/lib', '/opt', '/srv']
            root_paths = [Path(root) for root in roots]
            source_reconciliation = reconcile_sources(src, root_paths, utcnow(), apply=False)
            source_reconciliation_backup = None
            if args.apply_safe and source_reconciliation['auto_updates']:
                source_reconciliation_backup, source_reconciliation_before_sha = create_verified_backup(
                    source_path, Path(args.backup_dir), run_id, 'source-reconciliation'
                )
                source_reconciliation = reconcile_sources(src, root_paths, utcnow(), apply=True)
                src.commit()
                source_reconciliation_after_sha = source_sha(source_path)
                sql = ("INSERT INTO remediation_actions("
                       "run_id,action_level,action_type,target_table,target_id,target_field,"
                       "before_value,after_value,rationale,backup_path,source_sha256_before,"
                       "source_sha256_after,verification_status,created_at) "
                       "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)")
                for item in source_reconciliation['results']:
                    if not item.get('needs_update'):
                        continue
                    dst.execute(sql, (
                        run_id, 'AUTO_FIX', 'reconcile_evidence_source_location',
                        'provenance_source_locations', item['provenance_id'], 'location',
                        None, item['location'],
                        f"Evidence source location reconciled using {item['match_method']}.",
                        str(source_reconciliation_backup), source_reconciliation_before_sha,
                        source_reconciliation_after_sha, item['status'], utcnow()
                    ))
            begin_reconciliation_cycle(dst)
            process_source_reconciliation(dst, source_reconciliation)
            summary = run(src, dst)
            finish_reconciliation_cycle(dst)
            summary.update({
                'open_findings': dst.execute("SELECT COUNT(*) FROM maintenance_findings WHERE status='open'").fetchone()[0],
                'pending_enrichment': dst.execute("SELECT COUNT(*) FROM enrichment_queue WHERE status='pending'").fetchone()[0],
                'pending_candidates': dst.execute("SELECT COUNT(*) FROM candidate_changes WHERE status='pending'").fetchone()[0],
            })
            summary.update({
                'source_locations_verified': source_reconciliation['verified'],
                'source_urls_declared': source_reconciliation['declared'],
                'source_location_candidates': source_reconciliation['candidates'],
                'source_location_ambiguous': source_reconciliation['ambiguous'],
                'source_locations_missing': source_reconciliation['missing'],
                'source_location_updates_applied': source_reconciliation.get('applied', 0),
                'source_reconciliation_backup': str(source_reconciliation_backup) if source_reconciliation_backup else None,
            })
            after_sha = source_sha(source_path)
            summary.update({
                'run_id': run_id,
                'source_sha256': before_sha,
                'source_sha256_after': after_sha,
                'autofix_planned': remediation['planned'],
                'autofix_applied': remediation['applied'],
                'autofix_backup': remediation['backup'],
            })
            dst.execute(
                "UPDATE maintenance_runs SET finished_at=?,source_sha256_after=?,status='ok',summary_json=? WHERE id=?",
                (utcnow(), after_sha, json.dumps(summary, sort_keys=True), run_id)
            )
            dst.commit()
        except Exception as exc:
            dst.execute(
                "UPDATE maintenance_runs SET finished_at=?,source_sha256_after=?,status='failed',summary_json=? WHERE id=?",
                (utcnow(), source_sha(source_path), json.dumps({'error': str(exc)}), run_id)
            )
            dst.commit()
            raise

    print(json.dumps(summary, sort_keys=True) if args.json else summary)


if __name__ == '__main__':
    main()
