#!/usr/bin/env python3
"""Publish a verified Contacts OpenPGP key in WKD advanced-method layout."""
from __future__ import annotations
import argparse, hashlib, json, os, pathlib, subprocess, tempfile
from publish_openpgp_public_key import load_key, PublishError, atomic_write

class WKDError(RuntimeError): pass

def wkd_hash(email: str) -> str:
    local, sep, domain = email.strip().casefold().partition('@')
    if not sep or not local or domain != 'ww.cx':
        raise WKDError('WKD publisher is restricted to ww.cx addresses')
    p = subprocess.run(['gpg-wks-client','--print-wkd-hash',email],capture_output=True,text=True,check=False,timeout=15)
    if p.returncode != 0 or not p.stdout.strip():
        raise WKDError('unable to derive WKD hash')
    token = p.stdout.split()[0].strip()
    if len(token) < 20 or '/' in token or '..' in token:
        raise WKDError('invalid WKD hash output')
    return token

def dearmor_public(armor: str) -> bytes:
    if 'PRIVATE KEY' in armor or 'BEGIN PGP PUBLIC KEY BLOCK' not in armor:
        raise WKDError('unsafe OpenPGP material')
    p = subprocess.run(['gpg','--batch','--yes','--dearmor'],input=armor.encode(),capture_output=True,check=False,timeout=15)
    if p.returncode != 0 or not p.stdout:
        raise WKDError('public key dearmor failed')
    return p.stdout

def publish(database:pathlib.Path, contact_point_id:int, webroot:pathlib.Path)->dict:
    key=load_key(database,contact_point_id)
    email=key['email_address'].casefold()
    h=wkd_hash(email)
    binary=dearmor_public(key['public_key_armored'])
    root=webroot/'.well-known/openpgpkey/ww.cx'
    target=root/'hu'/h
    policy=root/'policy'
    atomic_write(target,binary)
    atomic_write(policy,b'')
    meta={
      'contract':'wwcx.openpgp-wkd-publication.v1',
      'email_address':email,
      'fingerprint':key['fingerprint'],
      'verification_status':key['verification_status'],
      'wkd_hash':h,
      'relative_path':f'.well-known/openpgpkey/ww.cx/hu/{h}',
      'sha256':hashlib.sha256(binary).hexdigest(),
      'private_key_material_included':False,
    }
    atomic_write(root/'publication.json',(json.dumps(meta,indent=2)+'\n').encode())
    return meta

def main():
    p=argparse.ArgumentParser();p.add_argument('--database',type=pathlib.Path,default=pathlib.Path('/var/lib/edge1-phone-intelligence/phone-intelligence.sqlite'));p.add_argument('--contact-point-id',type=int,required=True);p.add_argument('--webroot',type=pathlib.Path,default=pathlib.Path('/var/www/edge1-status'));a=p.parse_args()
    print(json.dumps(publish(a.database,a.contact_point_id,a.webroot),indent=2))
if __name__=='__main__': main()
