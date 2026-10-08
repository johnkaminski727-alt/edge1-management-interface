#!/usr/bin/env python3
"""Loopback-only, allowlisted service action broker for AVA Executive.

No caller-supplied command, unit name, path, environment, or arguments are accepted.
"""
from __future__ import annotations
import json, os, pwd, subprocess, uuid
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer

HOST='127.0.0.1'; PORT=8801; ORIGIN='https://edge1.ww.cx'
REGISTRY=Path('/opt/edge1-management-interface/config/ava-executive-capabilities.json')
WORKFLOW_INBOX=Path('/var/lib/wwcx-ava-office-manager/workflow-inbox')
ACTIONS={
 'security-spamhaus-refresh':'edge1-spamhaus-refresh.service',
 'security-suricata-update':'wwcx-suricata-update.service',
 'automation-self-heal':'edge1-service-self-heal.service',
 'mail-document-filing':'edge1-document-filing.service',
 'mail-contact-intake':'edge1-mail-contact-intake.service',
 'accounting-intake':'edge1-accounting-intake.service',
 'report-daily-briefing':'edge1-ava-daily-briefing.service',
 'report-weekly-briefing':'edge1-weekly-executive-briefing.service',
 'automation-watchdog':'edge1-automation-watchdog.service',
 'evidence-integrity':'edge1-evidence-integrity.service',
 'backup-verification':'edge1-backup-verification.service',
 'operations-intelligence-refresh':'edge1-ava-operations-intelligence.service'
}


def registered_workflows():
 data=json.loads(REGISTRY.read_text(encoding='utf-8'))
 return {str(w['id']):w for w in data.get('workflows',[]) if isinstance(w,dict) and w.get('autonomous') is True and w.get('id')}

def submit_workflow(workflow_id:str, objective:str=''):
 flows=registered_workflows()
 if workflow_id not in flows: raise ValueError('workflow is not registered for autonomous dispatch')
 objective=str(objective or '').strip()
 if len(objective)>1000: raise ValueError('objective too long')
 req_id=uuid.uuid4().hex
 payload={'workflow_id':workflow_id,'trigger_type':'owner-delegation','trigger_ref':'owner:'+req_id,'requested_by':'owner-via-ava','priority':'normal'}
 if objective: payload['objective']=objective
 WORKFLOW_INBOX.mkdir(parents=True,exist_ok=True)
 target=WORKFLOW_INBOX/(req_id+'.json'); tmp=WORKFLOW_INBOX/('.'+req_id+'.tmp')
 tmp.write_text(json.dumps(payload,sort_keys=True,indent=2)+'\n',encoding='utf-8')
 info=pwd.getpwnam('wwadmin'); os.chown(tmp,info.pw_uid,info.pw_gid); os.chmod(tmp,0o640); os.replace(tmp,target)
 return {'status':'queued','workflow_id':workflow_id,'request_id':req_id,'objective':objective,'arbitrary_commands':False}

def send(h,status,payload):
 b=json.dumps(payload,separators=(',',':')).encode(); h.send_response(status); h.send_header('Content-Type','application/json; charset=utf-8'); h.send_header('Cache-Control','no-store'); h.send_header('X-Content-Type-Options','nosniff'); h.send_header('Content-Length',str(len(b))); h.end_headers(); h.wfile.write(b)

def run_action(action:str):
 unit=ACTIONS.get(action)
 if not unit: raise ValueError('unsupported action')
 p=subprocess.run(['/usr/bin/systemctl','start',unit],text=True,capture_output=True,timeout=300)
 result=subprocess.run(['/usr/bin/systemctl','show','-p','Result','--value',unit],text=True,capture_output=True,timeout=10)
 unit_result=(result.stdout or '').strip() or 'unknown'
 return {'action':action,'unit':unit,'status':'succeeded' if p.returncode==0 and unit_result in {'success','done'} else 'failed','exit_code':p.returncode,'unit_result':unit_result,'error':(p.stderr or '')[-2000:]}

class Handler(BaseHTTPRequestHandler):
 server_version='AvaDispatchAdmin/1'
 def log_message(self,fmt,*args): return
 def do_GET(self):
  if self.path=='/healthz': return send(self,200,{'ok':True,'actions':len(ACTIONS),'arbitrary_commands':False})
  return send(self,404,{'error':'not_found'})
 def do_POST(self):
  if self.path not in {'/api/actions','/api/workflows'}: return send(self,404,{'error':'not_found'})
  if self.headers.get('Origin')!=ORIGIN: return send(self,403,{'error':'origin_denied'})
  if not self.headers.get('Content-Type','').lower().startswith('application/json'): return send(self,415,{'error':'content_type_required'})
  try:
   n=int(self.headers.get('Content-Length','0'))
   if n<2 or n>4096: raise ValueError('invalid body length')
   body=json.loads(self.rfile.read(n))
   if not isinstance(body,dict): raise ValueError('request body must be an object')
   if self.path=='/api/workflows':
    result=submit_workflow(str(body.get('workflow_id') or ''),str(body.get('objective') or ''))
    return send(self,202,result)
   result=run_action(str(body.get('action') or ''))
   return send(self,200 if result['status']=='succeeded' else 409,result)
  except (ValueError,json.JSONDecodeError) as exc: return send(self,400,{'error':'validation_failed','detail':str(exc)})
  except subprocess.TimeoutExpired: return send(self,504,{'error':'action_timed_out'})
  except Exception: return send(self,500,{'error':'action_failed'})

def main(): ThreadingHTTPServer((HOST,PORT),Handler).serve_forever()
if __name__=='__main__': main()
