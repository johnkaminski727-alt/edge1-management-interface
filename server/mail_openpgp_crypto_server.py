#!/usr/bin/env python3
"""Unix-socket OpenPGP crypto boundary for WW.CX Mail Room."""
from __future__ import annotations
import argparse, base64, json, os, pathlib, socketserver
from typing import Any
from mail_openpgp_crypto import GPGEngine,OpenPGPCryptoError

MAX_REQUEST=16*1024*1024
class ServerError(RuntimeError): pass
class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        try:
            line=self.rfile.readline(MAX_REQUEST+1)
            if not line or len(line)>MAX_REQUEST: raise ServerError('request size invalid')
            request=json.loads(line)
            response=self.server.application(request)
            self.wfile.write((json.dumps({'ok':True,'result':response},separators=(',',':'))+'\n').encode())
        except Exception as exc:
            self.wfile.write((json.dumps({'ok':False,'error':type(exc).__name__},separators=(',',':'))+'\n').encode())
class UnixServer(socketserver.ThreadingUnixStreamServer):
    daemon_threads=True

def load_config(path:pathlib.Path)->dict[str,Any]:
    data=json.loads(path.read_text())
    if data.get('contract')!='wwcx.openpgp-crypto-service.v1': raise ServerError('invalid service contract')
    return data

def make_app(config:dict[str,Any],engine:GPGEngine):
    def app(request:dict[str,Any]):
        op=request.get('operation')
        if op=='status':
            return {'contract':'wwcx.openpgp-crypto-status.v1','public_key_count':len(engine.fingerprints(False)),'secret_key_count':len(engine.fingerprints(True)),'encrypt_enabled':config['encrypt_enabled'],'decrypt_enabled':config['decrypt_enabled'],'sign_enabled':config['sign_enabled'],'private_key_export_supported':False}
        if op=='encrypt':
            if not config['encrypt_enabled']: raise ServerError('encryption disabled')
            signing=request.get('signing_fingerprint')
            if signing and not config['sign_enabled']: raise ServerError('signing disabled')
            raw=base64.b64decode(request['plaintext_b64'],validate=True)
            out=engine.encrypt(raw,list(request['recipient_fingerprints']),signing)
            return {'ciphertext_b64':base64.b64encode(out).decode(),'operation':'sign_encrypt' if signing else 'encrypt'}
        if op=='sign':
            if not config['sign_enabled']: raise ServerError('signing disabled')
            raw=base64.b64decode(request['plaintext_b64'],validate=True)
            out=engine.sign(raw,str(request['signing_fingerprint']))
            return {'signature_b64':base64.b64encode(out).decode(),'operation':'sign'}
        if op=='decrypt':
            if not config['decrypt_enabled']: raise ServerError('decryption disabled')
            raw=base64.b64decode(request['ciphertext_b64'],validate=True)
            out=engine.decrypt(raw)
            return {'plaintext_b64':base64.b64encode(out).decode()}
        raise ServerError('unsupported operation')
    return app

def main():
    p=argparse.ArgumentParser(); p.add_argument('--config',type=pathlib.Path,default=pathlib.Path('/etc/wwcx/openpgp-service.json')); p.add_argument('--homedir',type=pathlib.Path,default=pathlib.Path('/var/lib/wwcx-openpgp/gnupg')); p.add_argument('--socket',type=pathlib.Path,default=pathlib.Path('/run/wwcx-openpgp/crypto.sock')); a=p.parse_args()
    cfg=load_config(a.config); a.socket.parent.mkdir(parents=True,exist_ok=True)
    try: a.socket.unlink()
    except FileNotFoundError: pass
    with UnixServer(str(a.socket),Handler) as server:
        server.application=make_app(cfg,GPGEngine(a.homedir)); os.chmod(a.socket,0o660); server.serve_forever()
if __name__=='__main__': main()
