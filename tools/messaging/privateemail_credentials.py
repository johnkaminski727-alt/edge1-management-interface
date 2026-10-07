#!/usr/bin/env python3
"""Secure terminal-only mailbox credential enrollment; no messages are fetched."""
import getpass
import imaplib
import json
import os
from pathlib import Path
import ssl
import sys
import tempfile

ACCOUNTS = ("blank@ww.cx", "domaincontact@ww.cx", "webmaster@omegafx.com")
ROOT = Path("/etc/wwcx/privateemail-import")

def main():
    if os.geteuid() != 0:
        raise SystemExit("Run with sudo on Edge1.")
    if not sys.stdin.isatty():
        raise SystemExit("Use an interactive terminal; do not pass passwords as arguments.")
    ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    if ROOT.is_symlink():
        raise SystemExit("Unsafe credential directory.")
    ROOT.chmod(0o700)
    print("PrivateEmail migration credentials. Password entry is hidden.")
    print("Press Enter to skip an account. Originals will remain at PrivateEmail.")
    verified = []
    for account in ACCOUNTS:
        secret = getpass.getpass(account + " mailbox password: ")
        if not secret:
            print(account + ": skipped")
            continue
        client = None
        stage = "TLS connection"
        print(account + ": connecting and verifying…", flush=True)
        try:
            client = imaplib.IMAP4_SSL("mail.privateemail.com", 993,
                ssl_context=ssl.create_default_context(), timeout=25)
            stage = "mailbox login"
            status, _ = client.login(account, secret)
            if status != "OK":
                raise ValueError("login failed")
            stage = "folder listing"
            status, folders = client.list()
            if status != "OK":
                raise ValueError("folder inventory failed")
            stage = "secure credential storage"
            fd, temporary = tempfile.mkstemp(dir=ROOT, prefix=".credential-")
            try:
                os.fchmod(fd, 0o600)
                with os.fdopen(fd, "w") as f:
                    json.dump({"username": account, "password": secret}, f)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(temporary, ROOT / (account + ".json"))
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
            verified.append(account)
            print(account + ": verified; " + str(len(folders or [])) + " folders; credential stored root-only")
        except Exception as exc:
            print(account + ": failed at " + stage + " (" + type(exc).__name__ + "). Password was not saved.", flush=True)
        finally:
            secret = ""
            if client:
                try:
                    client.logout()
                except Exception:
                    pass
    print("Verified accounts: " + (", ".join(verified) or "none"))
    print("No messages fetched, sent, moved, or deleted.")

if __name__ == "__main__":
    main()
