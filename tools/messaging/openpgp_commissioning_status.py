#!/usr/bin/env python3
"""Read-only WW.CX OpenPGP production commissioning status."""
from __future__ import annotations
import argparse,json,pathlib,socket,sqlite3

def rpc_status(sock:pathlib.Path)->dict:
    s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);s.settimeout(3);s.connect(str(sock));s.sendall(b'{"operation":"status"}\n');line=s.makefile('rb').readline();s.close();r=json.loads(line);return r.get('result',{}) if r.get('ok') else {}
def main():
    p=argparse.ArgumentParser();p.add_argument('--database',type=pathlib.Path,default=pathlib.Path('/var/lib/edge1-phone-intelligence/phone-intelligence.sqlite'));p.add_argument('--contact-point-id',type=int,default=696);p.add_argument('--socket',type=pathlib.Path,default=pathlib.Path('/run/wwcx-openpgp/crypto.sock'));p.add_argument('--public-dir',type=pathlib.Path,default=pathlib.Path('/var/www/edge1-status/openpgp'));a=p.parse_args()
    svc=rpc_status(a.socket)
    con=sqlite3.connect(f'file:{a.database}?mode=ro',uri=True);con.row_factory=sqlite3.Row
    key=con.execute("select fingerprint,verification_status,revoked_at from contact_openpgp_keys where contact_point_id=? order by created_at desc,id desc limit 1",(a.contact_point_id,)).fetchone();pol=con.execute('select mode from contact_openpgp_policy where contact_point_id=?',(a.contact_point_id,)).fetchone();con.close()
    key=dict(key) if key else None; mode=pol['mode'] if pol else None
    asc=a.public_dir/'john-wwcx.asc';meta=a.public_dir/'john-wwcx.json'
    out={'contract':'wwcx.openpgp-commissioning-status.v1','service':svc,'contacts_key':key,'contacts_policy':mode,'public_key_published':asc.is_file() and meta.is_file(),'ready_for_sign_only':bool(svc.get('secret_key_count',0)>=1 and key and key['verification_status']=='verified' and not key['revoked_at'] and mode=='sign_only' and asc.is_file() and meta.is_file()),'private_key_export_supported':False}
    print(json.dumps(out,indent=2))
if __name__=='__main__':main()
