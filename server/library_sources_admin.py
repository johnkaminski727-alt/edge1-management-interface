"""Loopback-only admin/status API for the Edge1 Unified Library Source Catalog."""
from __future__ import annotations
import json, os, sqlite3, subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HOST='127.0.0.1'; PORT=int(os.environ.get('EDGE1_LIBRARY_SOURCES_ADMIN_PORT','8800'))
ORIGIN='https://edge1.ww.cx'
DB=Path('/var/lib/bigbird-ai-library/catalog/source-catalog.sqlite3')
STATUS_ROOT=Path('/var/www/edge1-status')
ALLOWED_ACTIONS={
 'refresh-catalog':['systemctl','start','edge1-library-source-catalog.service'],
 'reindex-evidence':['systemctl','start','edge1-library-external-index.service'],
 'extract-accounting':['systemctl','start','edge1-library-accounting-extract.service'],
 'run-intake':['systemctl','start','edge1-evidence-contacts-intake.service'],
}

def connect():
 c=sqlite3.connect(f'file:{DB}?mode=ro',uri=True); c.row_factory=sqlite3.Row; return c

def read_json(path):
 try:return json.loads(Path(path).read_text())
 except Exception:return None

def summary():
 with connect() as db:
  sources=db.execute('SELECT count(*) c FROM library_sources').fetchone()['c']; items=db.execute('SELECT count(*) c FROM library_items').fetchone()['c']
  preserved=db.execute("SELECT count(*) c FROM library_items WHERE copy_state='preserved'").fetchone()['c']
  indexed=db.execute('SELECT count(*) c FROM library_items WHERE library_document_id IS NOT NULL').fetchone()['c']
  accounting=db.execute('SELECT count(*) c FROM accounting_document_facts').fetchone()['c']
  deferred=db.execute("SELECT count(*) c FROM library_sources WHERE last_status='deferred'").fetchone()['c']
  errors=db.execute("SELECT count(*) c FROM library_sources WHERE last_status='failed' OR last_error IS NOT NULL").fetchone()['c']
  providers=[dict(r) for r in db.execute('SELECT provider,count(*) sources FROM library_sources GROUP BY provider ORDER BY provider')]
 return {'sources':sources,'items':items,'preserved':preserved,'indexed':indexed,'accounting_documents':accounting,'deferred_sources':deferred,'error_sources':errors,'providers':providers,
 'jobs':{'catalog':read_json(STATUS_ROOT/'library-source-catalog/status.json'),'indexer':read_json(STATUS_ROOT/'library-external-index/status.json'),'accounting':read_json(STATUS_ROOT/'library-accounting/status.json'),'intake':read_json(STATUS_ROOT/'evidence-contact-intake/status.json')}}

def sources():
 with connect() as db:
  q='''SELECT s.*,count(i.id) item_count,sum(CASE WHEN i.copy_state='preserved' THEN 1 ELSE 0 END) preserved_count,sum(CASE WHEN i.library_document_id IS NOT NULL THEN 1 ELSE 0 END) indexed_count FROM library_sources s LEFT JOIN library_items i ON i.source_id=s.id GROUP BY s.id ORDER BY s.provider,s.name'''
  rows=[dict(r) for r in db.execute(q)]
  for r in rows:
   rr=db.execute('SELECT * FROM library_sync_runs WHERE source_id=? ORDER BY id DESC LIMIT 1',(r['id'],)).fetchone(); r['last_run']=dict(rr) if rr else None
  return rows

def items(params):
 source=(params.get('source') or [''])[0]; term=(params.get('q') or [''])[0].strip(); limit=min(max(int((params.get('limit') or ['100'])[0]),1),500)
 where=[]; vals=[]
 if source: where.append('i.source_id=?'); vals.append(source)
 if term: where.append('(i.title LIKE ? OR i.source_path LIKE ? OR i.mime_type LIKE ?)'); vals += [f'%{term}%']*3
 sql='''SELECT i.id,i.source_id,s.provider,i.external_id,i.item_type,i.title,i.source_path,i.mime_type,i.size_bytes,i.provider_modified_at,i.content_sha256,i.copy_state,i.sync_state,i.evidence_source_document_id,i.library_document_id,i.last_seen_at FROM library_items i JOIN library_sources s ON s.id=i.source_id'''
 if where: sql+=' WHERE '+' AND '.join(where)
 sql+=' ORDER BY i.last_seen_at DESC,i.title LIMIT ?'; vals.append(limit)
 with connect() as db:return [dict(r) for r in db.execute(sql,vals)]

def accounting():
 with connect() as db:
  return [dict(r) for r in db.execute('''SELECT a.*,i.title,i.source_id,s.provider,i.evidence_source_document_id FROM accounting_document_facts a JOIN library_items i ON i.id=a.item_id JOIN library_sources s ON s.id=i.source_id ORDER BY coalesce(a.issue_date,'' ) DESC,i.title LIMIT 250''')]

def runs():
 with connect() as db:return [dict(r) for r in db.execute('SELECT r.*,s.name source_name,s.provider FROM library_sync_runs r LEFT JOIN library_sources s ON s.id=r.source_id ORDER BY r.id DESC LIMIT 100')]

def run_action(action, source_id=None):
 if action=='poll-source':
  if not source_id or not source_id.replace('-','').isalnum(): raise ValueError('valid source_id required')
  cmd=['/usr/bin/python3','-B','/opt/edge1-management-interface/tools/private_library/provider_poll.py','--source',source_id]
 elif action=='poll-all': cmd=['/usr/bin/python3','-B','/opt/edge1-management-interface/tools/private_library/provider_poll.py','--all']
 elif action in ALLOWED_ACTIONS: cmd=ALLOWED_ACTIONS[action]
 else: raise ValueError('unsupported action')
 p=subprocess.run(cmd,text=True,capture_output=True,timeout=120)
 return {'action':action,'source_id':source_id,'status':'succeeded' if p.returncode==0 else 'failed','exit_code':p.returncode,'output':(p.stdout or '')[-6000:],'error':(p.stderr or '')[-3000:]}

def send(h,status,payload):
 b=json.dumps(payload,separators=(',',':')).encode(); h.send_response(status); h.send_header('Content-Type','application/json; charset=utf-8'); h.send_header('Cache-Control','no-store'); h.send_header('X-Content-Type-Options','nosniff'); h.send_header('Content-Length',str(len(b))); h.end_headers(); h.wfile.write(b)

class Handler(BaseHTTPRequestHandler):
 server_version='Edge1LibrarySourcesAdmin/1'
 def log_message(self,fmt,*args):return
 def do_GET(self):
  p=urlparse(self.path); q=parse_qs(p.query)
  try:
   if p.path=='/healthz': return send(self,200,{'ok':True})
   if p.path=='/api/summary': return send(self,200,summary())
   if p.path=='/api/sources': return send(self,200,{'sources':sources()})
   if p.path=='/api/items': return send(self,200,{'items':items(q)})
   if p.path=='/api/accounting': return send(self,200,{'accounting':accounting()})
   if p.path=='/api/runs': return send(self,200,{'runs':runs()})
   return send(self,404,{'error':'not_found'})
  except Exception as exc:return send(self,500,{'error':'read_failed','detail':str(exc)})
 def do_POST(self):
  p=urlparse(self.path)
  if p.path!='/api/actions': return send(self,404,{'error':'not_found'})
  if self.headers.get('Origin')!=ORIGIN: return send(self,403,{'error':'origin_denied'})
  if not self.headers.get('Content-Type','').lower().startswith('application/json'): return send(self,415,{'error':'content_type_required'})
  try:
   n=int(self.headers.get('Content-Length','0'))
   if n<2 or n>8192: raise ValueError('invalid body length')
   body=json.loads(self.rfile.read(n)); action=str(body.get('action') or ''); source_id=body.get('source_id')
   result=run_action(action,source_id)
   return send(self,200 if result['status']=='succeeded' else 409,result)
  except (ValueError,json.JSONDecodeError) as exc:return send(self,400,{'error':'validation_failed','detail':str(exc)})
  except subprocess.TimeoutExpired:return send(self,504,{'error':'action_timed_out'})
  except Exception:return send(self,500,{'error':'action_failed'})

def main(): ThreadingHTTPServer((HOST,PORT),Handler).serve_forever()
if __name__=='__main__':main()
