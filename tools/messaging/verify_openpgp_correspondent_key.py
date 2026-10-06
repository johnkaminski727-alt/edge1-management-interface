#!/usr/bin/env python3
"""Promote a staged correspondent OpenPGP key after independent fingerprint confirmation."""
from __future__ import annotations
import argparse,json,pathlib,sqlite3
class VerifyError(RuntimeError): pass

def norm(fp:str)->str: return ''.join(fp.split()).upper()
def verify(database:pathlib.Path,email:str,fingerprint:str,method:str)->dict:
    fp=norm(fingerprint)
    if len(fp) not in {40,64} or any(c not in '0123456789ABCDEF' for c in fp): raise VerifyError('invalid fingerprint')
    if len(method.strip())<3: raise VerifyError('verification method is required')
    con=sqlite3.connect(database)
    try:
        row=con.execute('''select k.id,k.contact_point_id,k.fingerprint,k.verification_status from contact_openpgp_keys k join contact_points cp on cp.id=k.contact_point_id where cp.point_type='email' and lower(cp.normalized_value)=lower(?) and upper(k.fingerprint)=? and k.revoked_at is null''',(email,fp)).fetchone()
        if not row: raise VerifyError('staged key not found for email/fingerprint')
        con.execute("update contact_openpgp_keys set verification_status='verified', source=source || '; verified:' || ?, updated_at=CURRENT_TIMESTAMP where id=?",(method.strip(),row[0]))
        con.commit()
    except Exception:
        con.rollback(); raise
    finally: con.close()
    return {'email_address':email.casefold(),'fingerprint':fp,'verification_status':'verified','verification_method':method.strip(),'private_key_material_stored':False}

def main():
    p=argparse.ArgumentParser(); p.add_argument('--database',type=pathlib.Path,default=pathlib.Path('/var/lib/edge1-phone-intelligence/phone-intelligence.sqlite')); p.add_argument('--email',required=True); p.add_argument('--fingerprint',required=True); p.add_argument('--method',required=True); a=p.parse_args(); print(json.dumps(verify(a.database,a.email,a.fingerprint,a.method),indent=2))
if __name__=='__main__': main()
