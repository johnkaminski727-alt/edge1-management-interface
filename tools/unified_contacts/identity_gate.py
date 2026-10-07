"""Duplicate-prevention gate for Unified Contacts ingestion.

Incoming identities must be reconciled before canonical creation. Exact normalized
canonical/alias matches resolve to existing entities. Strong near-matches are
blocked for review rather than creating a second canonical entity.
"""
from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher


def normalize_identity_name(value: str | None) -> str:
    text = unicodedata.normalize('NFKD', value or '')
    text = ''.join(ch for ch in text if not unicodedata.combining(ch)).casefold()
    text = text.replace('&', ' and ')
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return ' '.join(text.split())


def _rows(db, entity_type: str):
    canonical = db.execute(
        """SELECT id, entity_type, canonical_name, 'canonical' AS match_source
           FROM contact_entities
           WHERE entity_type=? AND lifecycle_status<>'retired'""",
        (entity_type,),
    ).fetchall()
    aliases = db.execute(
        """SELECT e.id, e.entity_type, a.alias_name AS canonical_name, 'alias' AS match_source
           FROM contact_entity_aliases a
           JOIN contact_entities e ON e.id=a.entity_id
           WHERE e.entity_type=? AND e.lifecycle_status<>'retired'
             AND a.confidence<>'disputed'""",
        (entity_type,),
    ).fetchall()
    return list(canonical) + list(aliases)


def source_record_entity(db, source_record_id: str | None):
    if not source_record_id:
        return None
    rows = db.execute(
        """SELECT DISTINCT entity_id
           FROM contact_attestations
           WHERE entity_id IS NOT NULL
             AND attribute IN ('source_record_id','register_contact_id')
             AND attested_value=?
             AND verification_status<>'disputed'""",
        (source_record_id,),
    ).fetchall()
    ids = sorted({r[0] for r in rows})
    if len(ids) > 1:
        return {'status':'ambiguous','entity_ids':ids,'basis':'source_record_id'}
    if ids:
        return {'status':'existing','entity_id':ids[0],'basis':'source_record_id'}
    return None


def match_entity(db, entity_type: str, incoming_name: str, source_record_id: str | None = None,
                 near_threshold: float = 0.94, exclude_entity_id: int | None = None):
    source_match = source_record_entity(db, source_record_id)
    if source_match:
        return source_match

    key = normalize_identity_name(incoming_name)
    if not key:
        return {'status':'review','basis':'empty_normalized_name','candidates':[]}

    exact = {}
    candidates = []
    for row in _rows(db, entity_type):
        if exclude_entity_id is not None and row[0] == exclude_entity_id:
            continue
        row_key = normalize_identity_name(row[2])
        if not row_key:
            continue
        if row_key == key:
            exact[row[0]] = {'entity_id':row[0], 'name':row[2], 'source':row[3]}
            continue
        score = SequenceMatcher(None, key, row_key).ratio()
        if score >= near_threshold:
            candidates.append({'entity_id':row[0], 'name':row[2], 'source':row[3], 'score':round(score,4)})

    if len(exact) == 1:
        item = next(iter(exact.values()))
        return {'status':'existing','entity_id':item['entity_id'],'basis':'normalized_'+item['source']}
    if len(exact) > 1:
        return {'status':'ambiguous','basis':'multiple_exact_normalized_matches','entity_ids':sorted(exact)}

    # Deduplicate candidate entities because canonical + alias can both match.
    best = {}
    for item in candidates:
        old = best.get(item['entity_id'])
        if old is None or item['score'] > old['score']:
            best[item['entity_id']] = item
    candidates = sorted(best.values(), key=lambda x:(-x['score'], x['entity_id']))
    if candidates:
        return {'status':'review','basis':'strong_near_match','candidates':candidates}
    return {'status':'new','basis':'no_existing_identity_match','candidates':[]}


def require_safe_entity_resolution(db, entity_type: str, incoming_name: str,
                                   source_record_id: str | None = None):
    result = match_entity(db, entity_type, incoming_name, source_record_id)
    if result['status'] == 'existing':
        return result['entity_id'], False, result
    if result['status'] == 'new':
        return None, True, result
    raise RuntimeError(
        f"duplicate-prevention gate requires review for {entity_type} {incoming_name!r}: {result}"
    )
