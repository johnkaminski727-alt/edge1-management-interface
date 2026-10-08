#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB = Path('/var/lib/edge1-phone-intelligence/phone-intelligence.sqlite')
ROOT = Path('/var/lib/edge1-evidence-intake')


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def safe_name(value: str) -> str:
    return ''.join(ch if ch.isalnum() or ch in '._-' else '_' for ch in value).strip('._') or 'source'


def ensure_manifest_dir() -> Path:
    p = ROOT / 'manifests'
    p.mkdir(parents=True, exist_ok=True)
    return p


def register_source(db: sqlite3.Connection, *, document_type: str, source_name: str,
                    source_reference: str | None, verification_status: str,
                    notes: str | None, digest: str | None = None,
                    statement_date: str | None = None, account_reference: str | None = None) -> int:
    row = db.execute(
        'SELECT id FROM source_documents WHERE document_type=? AND source_name=?',
        (document_type, source_name),
    ).fetchone()
    if row:
        source_id = int(row[0])
        db.execute(
            '''UPDATE source_documents SET source_reference=?,statement_date=?,account_reference=?,
               sha256=COALESCE(?,sha256),verification_status=?,notes=? WHERE id=?''',
            (source_reference, statement_date, account_reference, digest,
             verification_status, notes, source_id),
        )
        return source_id
    cur = db.execute(
        '''INSERT INTO source_documents(document_type,source_name,source_reference,statement_date,
           account_reference,sha256,verification_status,notes) VALUES(?,?,?,?,?,?,?,?)''',
        (document_type, source_name, source_reference, statement_date,
         account_reference, digest, verification_status, notes),
    )
    return int(cur.lastrowid)


def write_manifest(payload: dict) -> tuple[Path, str]:
    directory = ensure_manifest_dir()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    basename = safe_name(payload.get('source_name') or 'source')
    path = directory / f'{basename}-{stamp}.json'
    encoded = (json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False) + '\n').encode('utf-8')
    path.write_bytes(encoded)
    return path, hashlib.sha256(encoded).hexdigest()


def register_manifest(args) -> dict:
    payload = {
        'contract': 'edge1.evidence-intake-manifest.v1',
        'captured_at': utcnow(),
        'source_system': args.source_system,
        'source_name': args.source_name,
        'source_reference': args.source_reference,
        'record_count': args.record_count,
        'verification_status': args.verification_status,
        'copy_status': args.copy_status,
        'notes': args.notes,
    }
    path, digest = write_manifest(payload)
    db = sqlite3.connect(DB)
    try:
        db.execute('BEGIN IMMEDIATE')
        source_id = register_source(
            db,
            document_type=args.document_type,
            source_name=args.source_name,
            source_reference=args.source_reference,
            verification_status=args.verification_status,
            notes=(args.notes or '') + f' Local intake manifest: {path}. Manifest SHA-256: {digest}.',
            digest=None,
        )
        db.commit()
    except Exception:
        db.rollback(); raise
    finally:
        db.close()
    return {'source_document_id': source_id, 'manifest': str(path), 'manifest_sha256': digest,
            'original_sha256': None, 'copy_status': args.copy_status}


def ingest_file(args) -> dict:
    source = Path(args.path)
    if not source.is_file():
        raise SystemExit(f'file not found: {source}')
    digest = sha256(source)
    target_dir = ROOT / 'objects' / digest[:2] / digest
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / source.name
    if not target.exists():
        shutil.copy2(source, target)
    if sha256(target) != digest:
        raise RuntimeError('evidence copy hash mismatch')
    manifest = {
        'contract': 'edge1.evidence-intake-manifest.v1', 'captured_at': utcnow(),
        'source_system': args.source_system, 'source_name': args.source_name or source.name,
        'source_reference': args.source_reference or str(source), 'copy_status': 'preserved_local',
        'local_copy': str(target), 'original_sha256': digest, 'size_bytes': source.stat().st_size,
        'verification_status': args.verification_status, 'notes': args.notes,
    }
    manifest_path, manifest_digest = write_manifest(manifest)
    db = sqlite3.connect(DB)
    try:
        db.execute('BEGIN IMMEDIATE')
        source_id = register_source(
            db, document_type=args.document_type, source_name=args.source_name or source.name,
            source_reference=args.source_reference or str(source), verification_status=args.verification_status,
            notes=(args.notes or '') + f' Preserved local copy: {target}. Intake manifest: {manifest_path}.',
            digest=digest,
        )
        db.commit()
    except Exception:
        db.rollback(); raise
    finally:
        db.close()
    return {'source_document_id': source_id, 'local_copy': str(target), 'sha256': digest,
            'manifest': str(manifest_path), 'manifest_sha256': manifest_digest}


def main():
    ap = argparse.ArgumentParser(description='Preserve/register external evidence sources for Unified Contacts.')
    sub = ap.add_subparsers(dest='command', required=True)
    m = sub.add_parser('register-manifest')
    m.add_argument('--source-system', required=True); m.add_argument('--source-name', required=True)
    m.add_argument('--source-reference', required=True); m.add_argument('--document-type', default='contact-register')
    m.add_argument('--record-count', type=int); m.add_argument('--verification-status', choices=['recovered','verified','partial','missing'], default='partial')
    m.add_argument('--copy-status', choices=['remote_reference','connector_snapshot','copy_unavailable'], default='remote_reference')
    m.add_argument('--notes')
    f = sub.add_parser('ingest-file')
    f.add_argument('--path', required=True); f.add_argument('--source-system', required=True)
    f.add_argument('--source-name'); f.add_argument('--source-reference'); f.add_argument('--document-type', default='document')
    f.add_argument('--verification-status', choices=['recovered','verified','partial','missing'], default='recovered')
    f.add_argument('--notes')
    args = ap.parse_args()
    result = register_manifest(args) if args.command == 'register-manifest' else ingest_file(args)
    print(json.dumps(result, indent=2, sort_keys=True))

if __name__ == '__main__': main()
