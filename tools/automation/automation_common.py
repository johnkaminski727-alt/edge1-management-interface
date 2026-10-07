#!/usr/bin/env python3
from __future__ import annotations
import hashlib, importlib.util, sqlite3, sys
from datetime import datetime, timezone
from pathlib import Path

def utcnow(): return datetime.now(timezone.utc).isoformat()
def sha(value: str): return hashlib.sha256(value.encode()).hexdigest()

def load_library_engine(repo_root: Path):
    path=repo_root/'services/bigbird-ai-gateway/app/library_engine.py'
    spec=importlib.util.spec_from_file_location('edge1_automation_library_engine',path)
    mod=importlib.util.module_from_spec(spec); sys.modules[spec.name]=mod; spec.loader.exec_module(mod); return mod

def upsert_library_document(db_path: Path, repo_root: Path, source_path: str, title: str, text: str, *, classification='internal'):
    if not db_path.is_file(): raise RuntimeError('Private Library database missing')
    engine=load_library_engine(repo_root)
    if engine.contains_secret(text): raise RuntimeError('document failed Private Library secret guard')
    ident=sha(source_path); stamp=utcnow(); chunks=[text[i:i+2400] for i in range(0,len(text),2200)] or ['']
    with sqlite3.connect(db_path) as db:
        db.execute('PRAGMA foreign_keys=ON')
        db.execute("""INSERT INTO documents(id,collection,title,source_path,classification,updated_at)
          VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET title=excluded.title,source_path=excluded.source_path,
          classification=excluded.classification,updated_at=excluded.updated_at""",(ident,'operations',title,source_path,classification,stamp))
        db.execute('DELETE FROM chunks WHERE document_id=?',(ident,))
        for i,chunk in enumerate(chunks): db.execute('INSERT INTO chunks(document_id,chunk_index,locator,text) VALUES(?,?,?,?)',(ident,i,f'characters {i*2200}–{min(i*2200+2400,len(text))}',chunk))
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok': raise RuntimeError('Private Library integrity check failed')
    return {'source_path':source_path,'chunks':len(chunks),'sha256':hashlib.sha256(text.encode()).hexdigest()}
