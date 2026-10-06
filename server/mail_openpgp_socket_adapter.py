#!/usr/bin/env python3
from __future__ import annotations
import base64,json,pathlib,socket
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from typing import Any,Callable
CONTRACT='wwcx.mail-openpgp-transform.v1'
DEFAULT_SOCKET=pathlib.Path('/run/wwcx-openpgp/crypto.sock')
MAX_RESPONSE=24*1024*1024
class OpenPGPAdapterError(RuntimeError): pass

def _rpc(request:dict[str,Any],socket_path:pathlib.Path=DEFAULT_SOCKET)->dict[str,Any]:
    body=(json.dumps(request,separators=(',',':'))+'\n').encode()
    try:
        client=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);client.settimeout(60);client.connect(str(socket_path));client.sendall(body)
        line=client.makefile('rb').readline(MAX_RESPONSE+1);client.close()
    except OSError as exc:
        raise OpenPGPAdapterError('isolated OpenPGP service unavailable') from exc
    if not line or len(line)>MAX_RESPONSE: raise OpenPGPAdapterError('isolated OpenPGP response invalid')
    try: response=json.loads(line)
    except json.JSONDecodeError as exc: raise OpenPGPAdapterError('isolated OpenPGP response invalid') from exc
    if response.get('ok') is not True or not isinstance(response.get('result'),dict): raise OpenPGPAdapterError('isolated OpenPGP operation refused')
    return response['result']

def _inner_mime(message:EmailMessage)->bytes:
    keep={'mime-version','content-type','content-transfer-encoding','content-disposition','content-id','content-description'}
    inner=EmailMessage(policy=policy.SMTP)
    for name,value in message.items():
        if name.casefold() in keep: inner[name]=value
    raw=message.as_bytes(policy=policy.SMTP);marker=b'\r\n\r\n';pos=raw.find(marker)
    if pos<0: raise OpenPGPAdapterError('plaintext MIME has no body boundary')
    body=raw[pos+len(marker):]
    inner.set_payload(body.decode('utf-8','replace'))
    return inner.as_bytes(policy=policy.SMTP)

def _outer_headers(source:EmailMessage,target:EmailMessage)->None:
    for name,value in source.items():
        lower=name.casefold()
        if lower=='mime-version' or lower.startswith('content-'): continue
        target[name]=value

def transform(plaintext:bytes,request:dict[str,Any],*,rpc:Callable[[dict[str,Any]],dict[str,Any]]|None=None)->dict[str,Any]:
    if not isinstance(request,dict): raise OpenPGPAdapterError('OpenPGP transform request is invalid')
    recipients=request.get('recipient_fingerprints')
    if not isinstance(recipients,list) or not recipients: raise OpenPGPAdapterError('verified recipient fingerprints are required')
    operation=str(request.get('operation','encrypt'))
    if operation not in {'encrypt','sign_encrypt'}: raise OpenPGPAdapterError('unsupported OpenPGP transform operation')
    source=BytesParser(policy=policy.SMTP).parsebytes(plaintext)
    if not isinstance(source,EmailMessage): raise OpenPGPAdapterError('plaintext MIME is invalid')
    service_request={'operation':'encrypt','plaintext_b64':base64.b64encode(_inner_mime(source)).decode(),'recipient_fingerprints':recipients}
    signing=request.get('signing_fingerprint')
    if operation=='sign_encrypt':
        if not isinstance(signing,str) or not signing.strip(): raise OpenPGPAdapterError('signing fingerprint is required')
        service_request['signing_fingerprint']=signing.strip()
    result=(rpc or _rpc)(service_request)
    try: armor=base64.b64decode(result['ciphertext_b64'],validate=True).decode('ascii')
    except Exception as exc: raise OpenPGPAdapterError('isolated OpenPGP ciphertext is invalid') from exc
    if '-----BEGIN PGP MESSAGE-----' not in armor: raise OpenPGPAdapterError('isolated OpenPGP ciphertext is not armored')
    outer=EmailMessage(policy=policy.SMTP);_outer_headers(source,outer)
    outer.set_type('multipart/encrypted');outer.set_param('protocol','application/pgp-encrypted')
    version=EmailMessage(policy=policy.SMTP);version.set_type('application/pgp-encrypted');version.set_payload('Version: 1\r\n')
    encrypted=EmailMessage(policy=policy.SMTP);encrypted.set_type('application/octet-stream');encrypted.set_payload(armor)
    outer.attach(version);outer.attach(encrypted)
    return {'contract':CONTRACT,'mime_bytes':outer.as_bytes(policy=policy.SMTP),'operation':operation,'signing_fingerprint':signing if operation=='sign_encrypt' else None,'recipient_fingerprints':list(recipients)}
