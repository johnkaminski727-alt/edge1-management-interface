#!/usr/bin/env python3
"""Stage an external correspondent OpenPGP public key in Contacts.

This tool never marks a newly received external key as verified. Verification is a
separate explicit action after the fingerprint is confirmed through an independent
channel.
"""
from __future__ import annotations
import argparse,json,pathlib,sqlite3,subprocess

class IntakeError(RuntimeError): pass

def inspect_key(path:pathlib.Path,expected_email:str)->dict:
    armor=path.read_text(encoding='utf-8')
    if 'PRIVATE KEY' in armor or 'BEGIN PGP PUBLIC KEY BLOCK' not in armor:
        raise IntakeError('input must contain public key material only')
    p=subprocess.run(['gpg','--batch','--no-tty','--with-colons','--import-options','show-only','--dry-run','--import',str(path)],capture_output=True,text=True,check=False,timeout=20)
    if p.returncode!=0: raise IntakeError('public key inspection failed')
    fingerprints=[]; uids=[]; encryption_subkeys=[]; current=None
    for line in p.stdout.splitlines():
        f=line.split(':'); typ=f[0] if f else ''
        if typ in {'pub','sub'}:
            current={'type':typ,'caps':f[11] if len(f)>11 else '','expires_unix':int(f[6]) if len(f)>6 and f[6].isdigit() else None}
        elif typ=='fpr' and len(f)>9 and f[9]:
            fingerprints.append(f[9])
            if current and current['type']=='sub' and 'e' in current['caps'].lower():
                encryption_subkeys.append({'fingerprint':f[9],'expires_unix':current['expires_unix']})
            current=None
        elif typ=='uid' and len(f)>9: uids.append(f[9])
    if not fingerprints: raise IntakeError('public key fingerprint unavailable')
    if not any(expected_email.casefold() in uid.casefold() for uid in uids): raise IntakeError('expected email absent from key UID')
    if not encryption_subkeys: raise IntakeError('key has no encryption-capable subkey')
    return {'primary_fingerprint':fingerprints[0],'public_key_armored':armor,'uids':uids,'encryption_subkeys':encryption_subkeys}

def resolve_point(con,email:str)->int:
    rows=con.execute("select id from contact_points where point_type='email' and lower(normalized_value)=lower(?) order by id",(email,)).fetchall()
    if len(rows)!=1: raise IntakeError('email must resolve to exactly one Contacts email point before key intake')
    return int(rows[0][0])

def stage(database:pathlib.Path,email:str,key:dict,source:str,status:str)->dict:
    if status not in {'unverified','document_sourced'}: raise IntakeError('initial external key status must be unverified or document_sourced')
    con=sqlite3.connect(database)
    try:
        con.execute('PRAGMA foreign_keys=ON'); point=resolve_point(con,email)
        con.execute('''insert into contact_openpgp_keys(contact_point_id,fingerprint,public_key_armored,verification_status,source)
                       values(?,?,?,?,?)
                       on conflict(contact_point_id,fingerprint) do update set public_key_armored=excluded.public_key_armored,verification_status=excluded.verification_status,source=excluded.source,updated_at=CURRENT_TIMESTAMP''',
                    (point,key['primary_fingerprint'],key['public_key_armored'],status,source))
        con.execute('''insert into contact_openpgp_policy(contact_point_id,mode) values(?,?)
                       on conflict(contact_point_id) do update set mode=excluded.mode,updated_at=CURRENT_TIMESTAMP''',(point,'encrypt_if_verified_key'))
        con.commit()
    except Exception:
        con.rollback(); raise
    finally: con.close()
    return {'contact_point_id':point,'email_address':email.casefold(),'fingerprint':key['primary_fingerprint'],'verification_status':status,'mode':'encrypt_if_verified_key','encryption_subkey_count':len(key['encryption_subkeys']),'private_key_material_stored':False}

def main():
    p=argparse.ArgumentParser(); p.add_argument('--database',type=pathlib.Path,default=pathlib.Path('/var/lib/edge1-phone-intelligence/phone-intelligence.sqlite')); p.add_argument('--email',required=True); p.add_argument('--public-key-file',type=pathlib.Path,required=True); p.add_argument('--source',required=True); p.add_argument('--verification-status',choices=['unverified','document_sourced'],default='unverified'); a=p.parse_args()
    print(json.dumps(stage(a.database,a.email,inspect_key(a.public_key_file,a.email),a.source,a.verification_status),indent=2))
if __name__=='__main__': main()
