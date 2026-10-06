#!/usr/bin/env python3
"""Register a verified OpenPGP public key in Unified Contacts. Public material only."""
from __future__ import annotations
import argparse,json,pathlib,sqlite3,subprocess,tempfile

class RegistrationError(RuntimeError): pass

def inspect_public_key(path:pathlib.Path,expected_email:str)->dict:
    armor=path.read_text(encoding='utf-8')
    if 'PRIVATE KEY' in armor or 'BEGIN PGP PUBLIC KEY BLOCK' not in armor:
        raise RegistrationError('input must contain public key material only')
    p=subprocess.run(['gpg','--batch','--no-tty','--with-colons','--import-options','show-only','--dry-run','--import',str(path)],capture_output=True,text=True,check=False,timeout=20)
    if p.returncode!=0: raise RegistrationError('public key inspection failed')
    fingerprints=[];uids=[]
    for line in p.stdout.splitlines():
        f=line.split(':')
        if f and f[0]=='fpr' and len(f)>9 and f[9] not in fingerprints: fingerprints.append(f[9])
        if f and f[0]=='uid' and len(f)>9: uids.append(f[9])
    if not fingerprints: raise RegistrationError('public key fingerprint unavailable')
    if not any(expected_email.casefold() in uid.casefold() for uid in uids):
        raise RegistrationError('expected email is absent from public key user IDs')
    return {'fingerprint':fingerprints[0],'public_key_armored':armor,'uids':uids}

def register(database:pathlib.Path,contact_point_id:int,expected_email:str,key:dict,mode:str='sign_only')->dict:
    if mode not in {'disabled','sign_only','encrypt_if_verified_key','require_encryption'}: raise RegistrationError('invalid OpenPGP policy mode')
    con=sqlite3.connect(database)
    try:
        con.execute('PRAGMA foreign_keys=ON')
        row=con.execute('select point_type,normalized_value from contact_points where id=?',(contact_point_id,)).fetchone()
        if row is None or row[0]!='email' or row[1].casefold()!=expected_email.casefold(): raise RegistrationError('contact point does not match expected email')
        con.execute('''insert into contact_openpgp_keys(contact_point_id,fingerprint,public_key_armored,verification_status,source)
                       values(?,?,?,?,?)
                       on conflict(contact_point_id,fingerprint) do update set public_key_armored=excluded.public_key_armored,verification_status='verified',source=excluded.source,updated_at=CURRENT_TIMESTAMP''',
                    (contact_point_id,key['fingerprint'],key['public_key_armored'],'verified','production_commissioning'))
        con.execute('''insert into contact_openpgp_policy(contact_point_id,mode) values(?,?)
                       on conflict(contact_point_id) do update set mode=excluded.mode,updated_at=CURRENT_TIMESTAMP''',(contact_point_id,mode))
        con.commit()
    except Exception:
        con.rollback(); raise
    finally: con.close()
    return {'contact_point_id':contact_point_id,'email_address':expected_email,'fingerprint':key['fingerprint'],'verification_status':'verified','mode':mode,'private_key_material_stored':False}

def main():
    p=argparse.ArgumentParser();p.add_argument('--database',type=pathlib.Path,default=pathlib.Path('/var/lib/edge1-phone-intelligence/phone-intelligence.sqlite'));p.add_argument('--contact-point-id',type=int,default=696);p.add_argument('--email',default='john@ww.cx');p.add_argument('--public-key-file',type=pathlib.Path,required=True);p.add_argument('--mode',default='sign_only');a=p.parse_args()
    print(json.dumps(register(a.database,a.contact_point_id,a.email,inspect_public_key(a.public_key_file,a.email),a.mode),indent=2))
if __name__=='__main__':main()
