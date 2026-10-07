#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, re, sqlite3
from pathlib import Path
from datetime import datetime, timezone
import sys
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT))
from tools.automation.automation_common import utcnow, upsert_library_document
LIB=Path('/var/lib/bigbird-ai-library/library.sqlite3'); STATUS=Path('/var/www/edge1-status/knowledge-consolidation/status.json')
def norm_title(v):return re.sub(r'[^a-z0-9]+',' ',(v or '').casefold()).strip()
def build():
    docs=[]
    with sqlite3.connect(f'file:{LIB}?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row
        for r in db.execute('SELECT id,collection,title,source_path,classification,updated_at FROM documents ORDER BY id'):
            text='\n'.join(x[0] for x in db.execute('SELECT text FROM chunks WHERE document_id=? ORDER BY chunk_index',(r['id'],)))
            docs.append({**dict(r),'text_sha256':hashlib.sha256(text.encode()).hexdigest(),'chars':len(text)})
    byhash={}; bytitle={}
    for d in docs:byhash.setdefault(d['text_sha256'],[]).append(d);bytitle.setdefault(norm_title(d['title']),[]).append(d)
    exact=[[{'title':x['title'],'source_path':x['source_path']} for x in g] for g in byhash.values() if len(g)>1 and g[0]['chars']>0]
    titles=[[{'title':x['title'],'source_path':x['source_path'],'sha256':x['text_sha256']} for x in g] for k,g in bytitle.items() if k and len(g)>1 and len({x['text_sha256'] for x in g})>1]
    return {'contract':'wwcx.knowledge-consolidation.v1','generated_at':utcnow(),'documents':len(docs),'exact_duplicate_groups':exact,'same_title_different_content_groups':titles,'review_items':len(exact)+len(titles),'mutation_performed':False,'merge_authorized':False}
def md(d):
    lines=['# Private Library Consolidation Review','',f"Generated: {d['generated_at']}",f"Documents: **{d['documents']}**",f"Review groups: **{d['review_items']}**",'', '## Exact duplicates','']
    for g in d['exact_duplicate_groups']:lines.append('- '+'; '.join(f"{x['title']} (`{x['source_path']}`)" for x in g))
    if not d['exact_duplicate_groups']:lines.append('- None.')
    lines += ['','## Same title, different content','']
    for g in d['same_title_different_content_groups']:lines.append('- '+'; '.join(f"{x['title']} (`{x['source_path']}`)" for x in g))
    if not d['same_title_different_content_groups']:lines.append('- None.')
    lines += ['','No documents were deleted, merged, or rewritten.']; return '\n'.join(lines)+'\n'
def main():
    d=build(); STATUS.parent.mkdir(parents=True,exist_ok=True); STATUS.write_text(json.dumps(d,indent=2)+'\n'); STATUS.chmod(0o644); upsert_library_document(LIB,ROOT,'operations/knowledge-consolidation/current.md','Private Library Consolidation Review',md(d)); print(json.dumps({'documents':d['documents'],'review_items':d['review_items']},sort_keys=True))
if __name__=='__main__':main()
