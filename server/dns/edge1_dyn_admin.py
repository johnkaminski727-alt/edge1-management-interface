#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, pathlib, re, subprocess, tempfile, time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ZONE='ww.cx.'
NSS=['ns1194.dns.dyn.com','ns2150.dns.dyn.com','ns3190.dns.dyn.com','ns4142.dns.dyn.com']
UPDATE='update.dyndns.com'
KEY=pathlib.Path('/etc/edge1-secrets/dyn/wwcx-tsig.key')
STATE=pathlib.Path('/var/lib/edge1-dyn')
AUDIT=STATE/'audit.jsonl'
STATUS=STATE/'status.json'
DKIM_FILE=pathlib.Path('/var/lib/wwcx-mail-gateway/wwcx-edge1-202610-dkim.txt')
OLD_SPF='v=spf1 include:spf.privateemail.com ~all'
NEW_SPF='v=spf1 ip4:89.126.248.191 include:spf.privateemail.com ~all'
DMARC='v=DMARC1; p=none; rua=mailto:dmarc@ww.cx; adkim=r; aspf=r; pct=100'
MAIL_IP='89.126.248.191'

def now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def sh(args, inp=None, timeout=12):
    r=subprocess.run(args,input=inp,text=True,capture_output=True,timeout=timeout)
    if r.returncode:
        msg=(r.stderr or r.stdout or ('command failed: '+args[0])).strip()
        raise RuntimeError(msg[:800])
    return r.stdout

def key_parts():
    name=hmac=''
    for line in KEY.read_text().splitlines():
        if line.startswith('Key Name\t'): name=line.split('\t',1)[1].strip()
        elif line.startswith('Key HMAC\t'): hmac=line.split('\t',1)[1].strip()
    if not name or not hmac: raise RuntimeError('TSIG key file is not parseable')
    return name,hmac

def dkim_value():
    txt=DKIM_FILE.read_text()
    chunks=re.findall(r'"([^"]*)"',txt)
    value=''.join(chunks).strip()
    if not value.startswith('v=DKIM1;') or 'p=' not in value: raise RuntimeError('DKIM public record is invalid')
    return value

def q(name,typ,ns=None):
    cmd=['/usr/bin/dig','+short']
    if ns: cmd.append('@'+ns)
    cmd += [name,typ]
    out=sh(cmd,timeout=6)
    return [x.strip() for x in out.splitlines() if x.strip()]

def esc_txt(v):
    chunks=[v[i:i+240] for i in range(0,len(v),240)] or ['']
    return ' '.join('"'+c.replace('\\','\\\\').replace('"','\\"')+'"' for c in chunks)
def update(lines):
    name,hmac=key_parts()
    body=[f'server {UPDATE}',f'zone {ZONE}',f'key {name} {hmac}',*lines,'send','']
    last=None
    for attempt in range(3):
        try:
            sh(['/usr/bin/nsupdate'], '\n'.join(body), timeout=12)
            return
        except Exception as exc:
            last=exc
            if attempt<2: time.sleep(2)
    raise last

def verify_exact(name,typ,expected):
    obs={ns:q(name,typ,ns) for ns in NSS}
    ok=True
    for vals in obs.values():
        norm=[]
        for v in vals:
            if typ=='TXT':
                parts=re.findall(r'"((?:\\.|[^"])*)"',v)
                joined=''.join(parts)
                joined=joined.replace('\\"','"').replace('\\\\','\\')
                norm.append(joined)
            else:
                norm.append(v)
        if expected not in norm: ok=False
    return ok,obs

def snapshot():
    return {'mail_a':q('mail.ww.cx','A'),'root_txt':q('ww.cx','TXT'),'dmarc':q('_dmarc.ww.cx','TXT'),'dkim':q('edge1-202610._domainkey.ww.cx','TXT'),'mx':q('ww.cx','MX')}

def write_status(extra=None):
    s=snapshot(); payload={'contract':'wwcx.dyn-dns-status.v1','generated_at':now(),'zone':'ww.cx','provider':'Dyn Standard DNS','tsig_configured':KEY.exists(),'authoritative_nameservers':NSS,'public':s,'precutover':{'mail_a':MAIL_IP,'spf':NEW_SPF,'dkim_selector':'edge1-202610','dmarc_policy':'p=none'},'mx_gate':'separate_explicit_approval'}
    if extra: payload.update(extra)
    STATE.mkdir(parents=True,exist_ok=True); tmp=STATUS.with_suffix('.tmp'); tmp.write_text(json.dumps(payload,indent=2)+'\n'); tmp.replace(STATUS)
    return payload

def audit(action,before,after,result):
    STATE.mkdir(parents=True,exist_ok=True)
    with AUDIT.open('a') as f: f.write(json.dumps({'at':now(),'action':action,'before':before,'after':after,'result':result},separators=(',',':'))+'\n')

def _ensure_record(name, typ, expected, update_lines):
    ok, obs = verify_exact(name, typ, expected)
    if ok:
        return {'ok': True, 'answers': obs, 'changed': False}
    err = None
    try:
        update(update_lines)
    except Exception as exc:
        err = str(exc)
    for delay in (4, 8, 12):
        time.sleep(delay)
        ok, obs = verify_exact(name, typ, expected)
        if ok:
            return {'ok': True, 'answers': obs, 'changed': True, 'transport_warning': err}
    return {'ok': False, 'answers': obs, 'changed': True, 'transport_error': err}

def apply_precutover():
    before=snapshot(); dk=dkim_value(); checks={}
    checks['mail.ww.cx']=_ensure_record('mail.ww.cx','A',MAIL_IP,[f'update add mail.ww.cx. 300 A {MAIL_IP}'])
    checks['ww.cx']=_ensure_record('ww.cx','TXT',NEW_SPF,[f'update add ww.cx. 300 TXT {esc_txt(NEW_SPF)}'])
    checks['edge1-202610._domainkey.ww.cx']=_ensure_record('edge1-202610._domainkey.ww.cx','TXT',dk,[f'update add edge1-202610._domainkey.ww.cx. 300 TXT {esc_txt(dk)}'])
    checks['_dmarc.ww.cx']=_ensure_record('_dmarc.ww.cx','TXT',DMARC,[f'update add _dmarc.ww.cx. 300 TXT {esc_txt(DMARC)}'])
    ok=all(x['ok'] for x in checks.values())
    after=snapshot(); audit('apply_precutover',before,after,{'ok':ok,'checks':checks}); write_status({'last_apply':{'at':now(),'ok':ok}})
    if not ok: raise RuntimeError('authoritative verification failed')
    return {'ok':True,'checks':checks,'before':before,'after':after}

def rollback_precutover():
    before=snapshot(); dk=dkim_value()
    update(['update delete mail.ww.cx. A'])
    update([f'update delete ww.cx. TXT {esc_txt(NEW_SPF)}',f'update add ww.cx. 300 TXT {esc_txt(OLD_SPF)}'])
    update(['update delete edge1-202610._domainkey.ww.cx. TXT'])
    update(['update delete _dmarc.ww.cx. TXT'])
    time.sleep(3); after=snapshot(); audit('rollback_precutover',before,after,{'ok':True}); write_status({'last_rollback':{'at':now(),'ok':True}}); return {'ok':True,'before':before,'after':after}

class H(BaseHTTPRequestHandler):
    def sendj(self,code,obj):
        b=(json.dumps(obj,indent=2)+'\n').encode(); self.send_response(code); self.send_header('Content-Type','application/json'); self.send_header('Cache-Control','no-store'); self.send_header('Content-Length',str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        if self.path=='/api/status':
            try:self.sendj(200,write_status())
            except Exception as e:self.sendj(500,{'ok':False,'error':str(e)})
        else:self.sendj(404,{'error':'not found'})
    def do_POST(self):
        try:
            n=int(self.headers.get('Content-Length','0')); data=json.loads(self.rfile.read(n) or b'{}')
            if self.path=='/api/apply-precutover':
                if data.get('confirm')!='WWCX_PRECUTOVER_DNS': raise ValueError('confirmation required')
                self.sendj(200,apply_precutover())
            elif self.path=='/api/rollback-precutover':
                if data.get('confirm')!='WWCX_PRECUTOVER_ROLLBACK': raise ValueError('confirmation required')
                self.sendj(200,rollback_precutover())
            elif self.path=='/api/apply-mx': self.sendj(409,{'ok':False,'error':'MX cutover is separately gated and not enabled in this phase'})
            else:self.sendj(404,{'error':'not found'})
        except Exception as e:self.sendj(400,{'ok':False,'error':str(e)})
    def log_message(self,*a): pass

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--listen',default='127.0.0.1'); ap.add_argument('--port',type=int,default=8798); a=ap.parse_args(); STATE.mkdir(parents=True,exist_ok=True); ThreadingHTTPServer((a.listen,a.port),H).serve_forever()
if __name__=='__main__': main()
