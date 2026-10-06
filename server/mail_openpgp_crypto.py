#!/usr/bin/env python3
"""Isolated GnuPG execution core for WW.CX OpenPGP service.

The caller receives fingerprints and ciphertext/plaintext only. Secret key bytes are
never returned, exported, logged, or read by application code.
"""
from __future__ import annotations
import os, pathlib, subprocess
from typing import Any

class OpenPGPCryptoError(RuntimeError): pass

class GPGEngine:
    def __init__(self, homedir: str|pathlib.Path):
        self.homedir=pathlib.Path(homedir)
    def _base(self)->list[str]:
        return ['gpg','--batch','--yes','--no-tty','--pinentry-mode','loopback','--homedir',str(self.homedir)]
    def _run(self,args:list[str],data:bytes=b'',timeout:int=30)->subprocess.CompletedProcess:
        try:
            p=subprocess.run(self._base()+args,input=data,capture_output=True,timeout=timeout,check=False)
        except (OSError,subprocess.TimeoutExpired) as exc: raise OpenPGPCryptoError('GnuPG execution failed') from exc
        if p.returncode!=0: raise OpenPGPCryptoError('GnuPG operation failed')
        return p
    def fingerprints(self, secret:bool=False)->list[str]:
        args=['--with-colons','--fingerprint','--list-secret-keys' if secret else '--list-keys']
        p=self._run(args)
        out=[]
        for line in p.stdout.decode('utf-8','replace').splitlines():
            f=line.split(':')
            if f and f[0]=='fpr' and len(f)>9 and f[9] and f[9] not in out: out.append(f[9])
        return out
    def encrypt(self, plaintext:bytes, recipients:list[str], signing_fingerprint:str|None=None)->bytes:
        if not plaintext or not recipients: raise OpenPGPCryptoError('plaintext and recipients are required')
        args=['--armor','--trust-model','always']
        if signing_fingerprint: args += ['--local-user',signing_fingerprint,'--sign']
        for fp in recipients: args += ['--recipient',fp]
        args += ['--encrypt']
        return self._run(args,plaintext,60).stdout
    def decrypt(self, ciphertext:bytes)->bytes:
        if not ciphertext: raise OpenPGPCryptoError('ciphertext is required')
        return self._run(['--decrypt'],ciphertext,60).stdout
