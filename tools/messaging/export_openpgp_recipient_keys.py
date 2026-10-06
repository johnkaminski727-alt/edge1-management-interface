#!/usr/bin/env python3
from __future__ import annotations
import argparse, datetime, json, pathlib, sqlite3, subprocess, tempfile
CONTRACT='wwcx.openpgp-recipient-keys.v1'
class RecipientExportError(RuntimeError): pass

def inspect_public_key(armor:str)->dict:
    if 'PRIVATE KEY' in armor or 'BEGIN PGP PUBLIC KEY BLOCK' not in armor:
        raise RecipientExportError('unsafe OpenPGP material')
    with tempfile.NamedTemporaryFile('w',suffix='.asc',delete=False) as f:
        f.write(armor); path=f.name
    try:
        p=subprocess.run(['gpg','--batch','--no-tty','--with-colons','--import-options','show-only','--dry-run','--import',path],capture_output=True,text=True,check=False,timeout=15)
    finally:
        pathlib.Path(path).unlink(missing_ok=True)
    if p.returncode!=0: raise RecipientExportError('public key inspection failed')
    primary=None; encryption=[]; current=None
    for line in p.stdout.splitlines():
        f=line.split(':'); kind=f[0] if f else ''
        if kind in {'pub','sub'}:
            current={'kind':kind,'caps':(f[11] if len(f)>11 else ''),'expires':(f[6] if len(f)>6 else '')}
        elif kind=='fpr' and current and len(f)>9:
            current['fingerprint']=f[9]
            if current['kind']=='pub' and primary is None: primary=f[9]
            if current['kind']=='sub' and 'e' in current['caps'].casefold(): encryption.append(dict(current))
            current=None
    if not primary or not encryption: raise RecipientExportError('verified key lacks encryption-capable subkey')
    return {'primary_fingerprint':primary,'encryption_subkeys':encryption}

def export(database:pathlib.Path)->dict:
    con=sqlite3.connect(f'file:{database}?mode=ro',uri=True); con.row_factory=sqlite3.Row
    try:
        rows=con.execute("""SELECT cp.id AS contact_point_id,cp.normalized_value AS email_address,k.fingerprint,k.public_key_armored,k.verification_status,k.revoked_at
            FROM contact_openpgp_keys k JOIN contact_points cp ON cp.id=k.contact_point_id
            WHERE cp.point_type='email' AND cp.lifecycle_status='active' AND k.verification_status='verified' AND k.revoked_at IS NULL
            ORDER BY cp.normalized_value,k.updated_at DESC,k.id DESC""").fetchall()
    finally: con.close()
    recipients={}
    for row in rows:
        email=row['email_address'].casefold()
        if email in recipients: continue
        info=inspect_public_key(row['public_key_armored'])
        if info['primary_fingerprint'] != row['fingerprint']: raise RecipientExportError('Contacts fingerprint mismatch')
        recipients[email]={'contact_point_id':row['contact_point_id'],'primary_fingerprint':row['fingerprint'],'verification_status':'verified','encryption_subkeys':[{'fingerprint':x['fingerprint'],'expires_unix':int(x['expires']) if x.get('expires') else None} for x in info['encryption_subkeys']]}
    return {'contract':CONTRACT,'generated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'recipients':recipients,'private_key_material_included':False,'armored_public_key_material_included':False}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--database',type=pathlib.Path,default=pathlib.Path('/var/lib/edge1-phone-intelligence/phone-intelligence.sqlite')); ap.add_argument('--output',type=pathlib.Path); a=ap.parse_args()
    text=json.dumps(export(a.database),indent=2)+'\n'
    if a.output: a.output.write_text(text)
    else: print(text,end='')
if __name__=='__main__': main()
