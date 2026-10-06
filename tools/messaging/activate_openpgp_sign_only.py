#!/usr/bin/env python3
"""Audit or activate WW.CX OpenPGP signing-only mode.

Default is audit-only. Apply requires every commissioning prerequisite and never
enables encryption or decryption.
"""
from __future__ import annotations
import argparse,json,os,pathlib,subprocess,tempfile
from openpgp_commissioning_status import rpc_status
import sqlite3

class ActivationError(RuntimeError): pass

def read_json(path:pathlib.Path)->dict:
    data=json.loads(path.read_text())
    if data.get('contract')!='wwcx.openpgp-crypto-service.v1': raise ActivationError('invalid service config contract')
    return data

def readiness(database:pathlib.Path,contact_point_id:int,sock:pathlib.Path,public_dir:pathlib.Path)->dict:
    svc=rpc_status(sock)
    con=sqlite3.connect(f'file:{database}?mode=ro',uri=True);con.row_factory=sqlite3.Row
    try:
        key=con.execute("select fingerprint,verification_status,revoked_at from contact_openpgp_keys where contact_point_id=? order by created_at desc,id desc limit 1",(contact_point_id,)).fetchone()
        pol=con.execute('select mode from contact_openpgp_policy where contact_point_id=?',(contact_point_id,)).fetchone()
    finally: con.close()
    key=dict(key) if key else None; mode=pol['mode'] if pol else None
    asc=public_dir/'john-wwcx.asc';meta=public_dir/'john-wwcx.json'
    available=bool(svc)
    checks={
      'service_status_available':available,
      'service_secret_key_present':available and svc.get('secret_key_count',0)>=1,
      'contacts_key_verified':bool(key and key.get('verification_status')=='verified' and not key.get('revoked_at')),
      'contacts_policy_sign_only':mode=='sign_only',
      'public_key_published':asc.is_file() and meta.is_file(),
      'encrypt_disabled':available and svc.get('encrypt_enabled') is False,
      'decrypt_disabled':available and svc.get('decrypt_enabled') is False,
    }
    return {'service':svc,'contacts_key':key,'contacts_policy':mode,'checks':checks,'ready':all(checks.values())}

def atomic_json(path:pathlib.Path,data:dict):
    st=path.stat() if path.exists() else None
    mode=(st.st_mode & 0o777) if st else 0o640
    uid=st.st_uid if st else 0
    gid=st.st_gid if st else 0
    fd,tmp=tempfile.mkstemp(prefix='.'+path.name+'.',dir=path.parent)
    try:
        with os.fdopen(fd,'w') as f: json.dump(data,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
        os.chmod(tmp,mode);os.chown(tmp,uid,gid);os.replace(tmp,path)
    finally:
        try: os.unlink(tmp)
        except FileNotFoundError: pass

def main():
    p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');p.add_argument('--database',type=pathlib.Path,default=pathlib.Path('/var/lib/edge1-phone-intelligence/phone-intelligence.sqlite'));p.add_argument('--contact-point-id',type=int,default=696);p.add_argument('--socket',type=pathlib.Path,default=pathlib.Path('/run/wwcx-openpgp/crypto.sock'));p.add_argument('--public-dir',type=pathlib.Path,default=pathlib.Path('/var/www/edge1-status/openpgp'));p.add_argument('--config',type=pathlib.Path,default=pathlib.Path('/etc/wwcx/openpgp-service.json'));a=p.parse_args()
    state=readiness(a.database,a.contact_point_id,a.socket,a.public_dir)
    out={'contract':'wwcx.openpgp-sign-only-activation.v1','mode':'apply' if a.apply else 'audit','ready':state['ready'],'checks':state['checks'],'applied':False}
    if a.apply:
        if os.geteuid()!=0: raise ActivationError('apply requires root')
        if not state['ready']: raise ActivationError('sign-only prerequisites are incomplete')
        cfg=read_json(a.config);cfg['sign_enabled']=True;cfg['encrypt_enabled']=False;cfg['decrypt_enabled']=False;cfg['allow_private_key_export']=False
        atomic_json(a.config,cfg)
        subprocess.run(['systemctl','restart','wwcx-openpgp-crypto.service'],check=True,timeout=30)
        post=rpc_status(a.socket)
        if post.get('sign_enabled') is not True or post.get('encrypt_enabled') is not False or post.get('decrypt_enabled') is not False:
            raise ActivationError('post-activation service state is unsafe')
        out['applied']=True;out['service']=post
    print(json.dumps(out,indent=2))
if __name__=='__main__': main()
