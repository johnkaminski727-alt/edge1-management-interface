"""Credential hashing helpers for Edge1 Communications Relay."""
from __future__ import annotations
import base64, hashlib, hmac, os
HASH_NAME='sha256'; SALT_BYTES=16

def hash_password(password: str, *, iterations: int=600_000, salt: bytes|None=None)->tuple[str,str]:
    if not password: raise ValueError('password must not be empty')
    actual_salt=salt or os.urandom(SALT_BYTES)
    digest=hashlib.pbkdf2_hmac(HASH_NAME,password.encode('utf-8'),actual_salt,iterations)
    return base64.b64encode(actual_salt).decode('ascii'), base64.b64encode(digest).decode('ascii')

def verify_password(password: str, salt_b64: str, digest_b64: str, *, iterations: int=600_000)->bool:
    try:
        salt=base64.b64decode(salt_b64.encode('ascii'),validate=True); expected=base64.b64decode(digest_b64.encode('ascii'),validate=True)
    except (ValueError,UnicodeError): return False
    actual=hashlib.pbkdf2_hmac(HASH_NAME,password.encode('utf-8'),salt,iterations)
    return hmac.compare_digest(actual,expected)
