#!/usr/bin/env python3
"""Publish a verified Contact OpenPGP public key; never reads secret keyrings."""
from __future__ import annotations
import argparse,hashlib,json,pathlib,sqlite3,tempfile,os

class PublishError(RuntimeError): pass

def load_key(database:pathlib.Path,contact_point_id:int)->dict:
    con=sqlite3.connect(f'file:{database}?mode=ro',uri=True); con.row_factory=sqlite3.Row
    try:
        row=con.execute('''
          SELECT k.fingerprint,k.public_key_armored,k.verification_status,k.source,
                 k.expires_at,k.revoked_at,cp.normalized_value AS email_address
          FROM contact_openpgp_keys k JOIN contact_points cp ON cp.id=k.contact_point_id
          WHERE k.contact_point_id=? AND k.verification_status='verified' AND k.revoked_at IS NULL
          ORDER BY k.created_at DESC,k.id DESC LIMIT 1
        ''',(contact_point_id,)).fetchone()
    finally: con.close()
    if row is None: raise PublishError('no verified active OpenPGP key for contact point')
    data=dict(row); armor=data['public_key_armored']
    if 'PRIVATE KEY' in armor or 'BEGIN PGP PUBLIC KEY BLOCK' not in armor:
        raise PublishError('stored OpenPGP material is not a safe public key')
    return data

def atomic_write(path:pathlib.Path,data:bytes,mode:int=0o644):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='.'+path.name+'.',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as f: f.write(data); f.flush(); os.fsync(f.fileno())
        os.chmod(tmp,mode); os.replace(tmp,path)
    finally:
        try: os.unlink(tmp)
        except FileNotFoundError: pass

def publish(database:pathlib.Path,contact_point_id:int,outdir:pathlib.Path,slug:str)->dict:
    key=load_key(database,contact_point_id)
    armor=(key['public_key_armored'].rstrip()+'\n').encode()
    asc=outdir/f'{slug}.asc'; meta=outdir/f'{slug}.json'
    metadata={
      'contract':'wwcx.openpgp-public-key.v1','email_address':key['email_address'],
      'fingerprint':key['fingerprint'],'verification_status':key['verification_status'],
      'source':key['source'],'expires_at':key['expires_at'],'sha256':hashlib.sha256(armor).hexdigest(),
      'private_key_material_included':False,'public_key_file':asc.name,
    }
    atomic_write(asc,armor); atomic_write(meta,(json.dumps(metadata,indent=2)+'\n').encode())
    return metadata

def main():
    p=argparse.ArgumentParser();p.add_argument('--database',type=pathlib.Path,default=pathlib.Path('/var/lib/edge1-phone-intelligence/phone-intelligence.sqlite'));p.add_argument('--contact-point-id',type=int,required=True);p.add_argument('--outdir',type=pathlib.Path,default=pathlib.Path('/var/www/edge1-status/openpgp'));p.add_argument('--slug',default='john-wwcx');a=p.parse_args()
    print(json.dumps(publish(a.database,a.contact_point_id,a.outdir,a.slug),indent=2))
if __name__=='__main__': main()
