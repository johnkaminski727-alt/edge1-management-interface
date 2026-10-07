#!/usr/bin/env python3
"""Conservative source-location reconciliation for Unified Contacts provenance."""
from __future__ import annotations

import hashlib
import os
import sqlite3
from pathlib import Path

LOCATION_DDL = '''
CREATE TABLE IF NOT EXISTS provenance_source_locations (
    provenance_id INTEGER PRIMARY KEY
        REFERENCES provenance_records(id) ON DELETE CASCADE,
    location_kind TEXT NOT NULL
        CHECK(location_kind IN ('local_file','web_url','internal_reference')),
    location TEXT NOT NULL,
    source_sha256 TEXT,
    match_method TEXT NOT NULL,
    verification_status TEXT NOT NULL
        CHECK(verification_status IN ('verified','declared','candidate','ambiguous','missing')),
    last_verified_at TEXT NOT NULL,
    notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_provenance_source_locations_status
ON provenance_source_locations(verification_status, location_kind);
'''


def ensure_schema(connection):
    connection.executescript(LOCATION_DDL)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def candidate_names(row) -> list[str]:
    names = []
    for value in (row['source_reference'], row['source_name']):
        value = (value or '').strip()
        if not value:
            continue
        name = Path(value).name
        if name and name not in names:
            names.append(name)
    return names


def index_named_files(roots: list[Path], wanted_names: set[str]) -> dict[str, list[Path]]:
    found = {name: [] for name in wanted_names}
    if not wanted_names:
        return found
    skip = {'proc', 'sys', 'dev', 'run', '.cache', '__pycache__', 'node_modules'}
    for root in roots:
        try:
            root = root.resolve()
        except OSError:
            continue
        if not root.exists() or not root.is_dir():
            continue
        for base, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d not in skip]
            for name in files:
                if name in wanted_names:
                    found.setdefault(name, []).append(Path(base) / name)
    return found


def index_private_library(library_db: Path | None, wanted_names: set[str]) -> dict[str, list[dict]]:
    """Index Private Library document metadata by filename.

    Private Library metadata is useful for locating a source, but because its
    current documents table does not retain source content hashes, a filename
    match alone is never considered verified evidence.
    """
    found = {name: [] for name in wanted_names}
    if not library_db or not library_db.is_file() or not wanted_names:
        return found
    try:
        con = sqlite3.connect(f'file:{library_db}?mode=ro', uri=True)
        con.row_factory = sqlite3.Row
        try:
            tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if 'documents' not in tables:
                return found
            for row in con.execute(
                "SELECT id,collection,title,source_path,classification,updated_at FROM documents"
            ):
                path = (row['source_path'] or '').strip()
                title = (row['title'] or '').strip()
                names = {Path(path).name if path else '', Path(title).name if title else ''}
                for name in names:
                    if name and name in wanted_names:
                        found.setdefault(name, []).append(dict(row))
        finally:
            con.close()
    except (OSError, sqlite3.Error):
        return found
    return found


def provenance_rows(connection):
    return connection.execute('''
        SELECT pr.id, pr.source_kind, pr.source_name, pr.source_reference,
               pr.source_url, pr.source_sha256, pr.verification_status,
               pr.source_document_id, sd.sha256 AS document_sha256
        FROM provenance_records pr
        LEFT JOIN source_documents sd ON sd.id=pr.source_document_id
        WHERE pr.source_kind IN ('document','register','email','public_source','import')
        ORDER BY pr.id
    ''').fetchall()


def existing_locations(connection) -> dict[int, dict]:
    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='provenance_source_locations'"
    ).fetchone()
    if not exists:
        return {}
    return {
        int(row['provenance_id']): dict(row)
        for row in connection.execute(
            "SELECT provenance_id,location_kind,location,source_sha256,match_method,verification_status FROM provenance_source_locations"
        )
    }


def location_needs_update(existing: dict | None, item: dict) -> bool:
    if not existing:
        return True
    expected = {
        'location_kind': item['location_kind'],
        'location': item['location'],
        'source_sha256': item['source_sha256'],
        'match_method': item['match_method'],
        'verification_status': item['status'],
    }
    return any(existing.get(key) != value for key, value in expected.items())


def _private_library_matches(row, library_index: dict[str, list[dict]]) -> list[dict]:
    matches = []
    seen = set()
    for name in candidate_names(row):
        for item in library_index.get(name, []):
            key = (item.get('id'), item.get('source_path'))
            if key not in seen:
                seen.add(key)
                matches.append(item)
    return matches


def reconcile(
    connection,
    roots: list[Path],
    now: str,
    apply: bool = False,
    library_db: Path | None = None,
) -> dict:
    rows = provenance_rows(connection)
    wanted = set()
    for row in rows:
        if row['source_kind'] == 'document':
            wanted.update(candidate_names(row))
    file_index = index_named_files(roots, wanted)
    library_index = index_private_library(library_db, wanted)

    results = []
    for row in rows:
        pid = int(row['id'])
        url = (row['source_url'] or '').strip()
        if url.startswith(('https://', 'http://')):
            results.append({
                'provenance_id': pid, 'status': 'declared', 'action_level': 'AUTO_FIX',
                'location_kind': 'web_url', 'location': url, 'match_method': 'source_url',
                'source_sha256': None,
            })
            continue
        if row['source_kind'] != 'document':
            continue

        reference = (row['source_reference'] or '').strip()
        declared = Path(reference) if reference else None
        expected_hash = (row['source_sha256'] or row['document_sha256'] or '').strip().lower()

        if declared and declared.is_absolute() and declared.is_file():
            actual_hash = sha256_file(declared)
            if expected_hash and actual_hash != expected_hash:
                results.append({
                    'provenance_id': pid, 'status': 'ambiguous', 'action_level': 'REVIEW_REQUIRED',
                    'location_kind': 'local_file', 'location': str(declared),
                    'match_method': 'declared_path_hash_mismatch', 'source_sha256': actual_hash,
                })
            else:
                results.append({
                    'provenance_id': pid, 'status': 'verified', 'action_level': 'AUTO_FIX',
                    'location_kind': 'local_file', 'location': str(declared),
                    'match_method': 'declared_path', 'source_sha256': actual_hash,
                })
            continue

        matches = []
        for name in candidate_names(row):
            matches.extend(file_index.get(name, []))
        matches = sorted({p.resolve() for p in matches if p.is_file()}, key=str)

        if expected_hash and matches:
            hash_matches = []
            for path in matches:
                try:
                    if sha256_file(path) == expected_hash:
                        hash_matches.append(path)
                except OSError:
                    pass
            if len(hash_matches) == 1:
                results.append({
                    'provenance_id': pid, 'status': 'verified', 'action_level': 'AUTO_FIX',
                    'location_kind': 'local_file', 'location': str(hash_matches[0]),
                    'match_method': 'sha256', 'source_sha256': expected_hash,
                })
                continue
            if len(hash_matches) > 1:
                results.append({
                    'provenance_id': pid, 'status': 'ambiguous', 'action_level': 'REVIEW_REQUIRED',
                    'location_kind': 'local_file', 'location': '\n'.join(map(str, hash_matches)),
                    'match_method': 'sha256_multiple', 'source_sha256': expected_hash,
                })
                continue

        if len(matches) == 1:
            results.append({
                'provenance_id': pid, 'status': 'candidate', 'action_level': 'AUTO_STAGE',
                'location_kind': 'local_file', 'location': str(matches[0]),
                'match_method': 'unique_filename', 'source_sha256': None,
            })
            continue
        if len(matches) > 1:
            results.append({
                'provenance_id': pid, 'status': 'ambiguous', 'action_level': 'REVIEW_REQUIRED',
                'location_kind': 'local_file', 'location': '\n'.join(map(str, matches)),
                'match_method': 'filename_multiple', 'source_sha256': None,
            })
            continue

        library_matches = _private_library_matches(row, library_index)
        if library_matches:
            exact = []
            ref_norm = reference.strip('/')
            for item in library_matches:
                source_path = (item.get('source_path') or '').strip()
                if source_path and source_path.strip('/') == ref_norm:
                    exact.append(item)
            if len(exact) == 1:
                item = exact[0]
                results.append({
                    'provenance_id': pid, 'status': 'declared', 'action_level': 'AUTO_FIX',
                    'location_kind': 'internal_reference',
                    'location': f"private-library:{item['id']}:{item['source_path']}",
                    'match_method': 'private_library_exact_source_path',
                    'source_sha256': expected_hash or None,
                })
                continue
            if len(library_matches) == 1:
                item = library_matches[0]
                results.append({
                    'provenance_id': pid, 'status': 'candidate', 'action_level': 'AUTO_STAGE',
                    'location_kind': 'internal_reference',
                    'location': f"private-library:{item['id']}:{item['source_path']}",
                    'match_method': 'private_library_unique_filename',
                    'source_sha256': expected_hash or None,
                })
                continue
            locations = [f"private-library:{item['id']}:{item['source_path']}" for item in library_matches]
            results.append({
                'provenance_id': pid, 'status': 'ambiguous', 'action_level': 'REVIEW_REQUIRED',
                'location_kind': 'internal_reference', 'location': '\n'.join(locations),
                'match_method': 'private_library_filename_multiple', 'source_sha256': expected_hash or None,
            })
            continue

        results.append({
            'provenance_id': pid, 'status': 'missing', 'action_level': 'AUTO_STAGE',
            'location_kind': 'local_file', 'location': reference or (row['source_name'] or ''),
            'match_method': 'not_found', 'source_sha256': expected_hash or None,
        })

    existing = existing_locations(connection)
    for item in results:
        item['needs_update'] = (
            item['action_level'] == 'AUTO_FIX'
            and location_needs_update(existing.get(item['provenance_id']), item)
        )

    if apply:
        ensure_schema(connection)
        for item in results:
            if item['action_level'] != 'AUTO_FIX' or not item['needs_update']:
                continue
            connection.execute('''
                INSERT INTO provenance_source_locations(
                    provenance_id,location_kind,location,source_sha256,match_method,
                    verification_status,last_verified_at,notes
                ) VALUES(?,?,?,?,?,?,?,?)
                ON CONFLICT(provenance_id) DO UPDATE SET
                    location_kind=excluded.location_kind,
                    location=excluded.location,
                    source_sha256=excluded.source_sha256,
                    match_method=excluded.match_method,
                    verification_status=excluded.verification_status,
                    last_verified_at=excluded.last_verified_at,
                    notes=excluded.notes
            ''', (
                item['provenance_id'], item['location_kind'], item['location'],
                item['source_sha256'], item['match_method'], item['status'], now,
                'Maintained automatically by Edge1 Contacts source reconciliation.'
            ))
    return {
        'results': results,
        'verified': sum(1 for r in results if r['status'] == 'verified'),
        'declared': sum(1 for r in results if r['status'] == 'declared'),
        'candidates': sum(1 for r in results if r['status'] == 'candidate'),
        'ambiguous': sum(1 for r in results if r['status'] == 'ambiguous'),
        'missing': sum(1 for r in results if r['status'] == 'missing'),
        'private_library_exact': sum(1 for r in results if r['match_method'] == 'private_library_exact_source_path'),
        'private_library_candidates': sum(1 for r in results if r['match_method'] == 'private_library_unique_filename'),
        'private_library_ambiguous': sum(1 for r in results if r['match_method'] == 'private_library_filename_multiple'),
        'auto_updates': sum(1 for r in results if r.get('needs_update')),
        'applied': sum(1 for r in results if apply and r.get('needs_update')),
    }
