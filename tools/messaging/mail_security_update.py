#!/usr/bin/env python3
"""Root-only scheduled signature/package maintenance, without reading mail."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import pwd
import shutil
import socket
import subprocess
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from server.mail_security_updates import STATE

PACKAGES = ['rspamd', 'clamav', 'clamav-base', 'clamav-daemon', 'clamav-freshclam', 'clamdscan', 'libclamav12']


def run(command, timeout=600, capture=False):
    return subprocess.run(command, check=True, timeout=timeout, text=True,
                          stdout=subprocess.PIPE if capture else subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def clam_command(command):
    with socket.socket(socket.AF_UNIX) as client:
        client.settimeout(15); client.connect('/run/wwcx-mail-clamd/scan.sock')
        client.sendall(('z'+command+'\0').encode())
        return client.recv(1024).decode().strip('\0\n')


def daily_version():
    for extension in ['cld', 'cvd']:
        path = Path('/var/lib/clamav/daily.'+extension)
        if path.exists(): return path.open('rb').read(512).decode('ascii', errors='replace').split(':')[2]
    raise RuntimeError('Definition database missing')


def versions():
    return {'clamav_loaded': clam_command('VERSION'),
            'packages': run(['dpkg-query', '-W', '-f=${Package}=${Version}\n', *PACKAGES], capture=True).stdout.splitlines()}


def scanner_probe():
    if clam_command('PING') != 'PONG': raise RuntimeError('Scanner unavailable')
    for data, expected in [(b'Harmless update acceptance probe', 0),
                           (b'X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*', 1)]:
        result = subprocess.run(['clamdscan','--config-file=/etc/clamav/wwcx-mail-clamd.conf','--stream','--no-summary','-'], input=data,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=90)
        if result.returncode != expected: raise RuntimeError('Malware probe failed')


def definitions():
    run(['freshclam', '--config-file=/etc/clamav/freshclam.conf', '--daemon-notify=/etc/clamav/wwcx-mail-clamd.conf'], timeout=1200)
    # Explicitly reload even when FreshClam found no changes (e.g. after recovery).
    if '/'+daily_version()+'/' not in clam_command('VERSION'):
        if 'RELOADING' not in clam_command('RELOAD'): raise RuntimeError('Reload not acknowledged')
    for _ in range(90):
        try:
            if '/'+daily_version()+'/' in clam_command('VERSION'): break
        except (OSError, TimeoutError): pass
        time.sleep(1)
    else: raise RuntimeError('Loaded definition version mismatch')
    scanner_probe()


def packages():
    # Signed existing APT sources only. No new repositories, removals or reboot.
    env = dict(os.environ, DEBIAN_FRONTEND='noninteractive', NEEDRESTART_MODE='l')
    run(['apt-get', '-o', 'APT::Update::Error-Mode=any', '-o', 'DPkg::Lock::Timeout=300', 'update'], timeout=1200)
    before = run(['dpkg-query','-W','-f=${Package}=${Version}\n', *PACKAGES], capture=True).stdout
    directory = STATE / ('backup-'+str(int(time.time())))
    directory.mkdir(mode=0o700)
    for source in ['/etc/rspamd/local.d','/etc/rspamd/override.d','/etc/clamav']:
        if Path(source).exists(): shutil.copytree(source, directory / Path(source).name)
    subprocess.run(['apt-get','-y','--only-upgrade','--no-remove','-o','DPkg::Lock::Timeout=300',
                    '-o','Dpkg::Options::=--force-confold','install', *PACKAGES], env=env,
                   check=True, timeout=1800, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # A package's postinstall must not create a competing updater.
    run(['systemctl','disable','--now','clamav-freshclam.service'])
    try:
        run(['rspamadm','configtest'])
    except Exception:
        run(['systemctl','stop','rspamd'])  # Hold new mail rather than run invalid rules.
        raise
    after = run(['dpkg-query','-W','-f=${Package}=${Version}\n', *PACKAGES], capture=True).stdout
    if before != after: run(['systemctl','restart','rspamd','wwcx-mail-clamd'], timeout=180)
    run(['systemctl','is-active','rspamd','wwcx-mail-clamd'])
    scanner_probe()
    # Check actual scoring after maintenance; no mailbox/AVA or database writes.
    from server.mail_room_security import rspamd_scan
    clean = rspamd_scan(b'From: update@example.test\nTo: update@example.test\nSubject: Update probe\n\nHarmless acceptance probe\n', {})
    spam = rspamd_scan(b'From: update@example.test\nTo: update@example.test\nSubject: Update probe\n\nXJS*C4JDBQADN1.NSBN3*2IDNEN*GTUBE-STANDARD-ANTI-UBE-TEST-EMAIL*C.34X\n', {})
    if clean.get('is_skipped') or 'GTUBE' not in spam.get('symbols', {}): raise RuntimeError('Spam rule probe failed')
    # Bounded private config backups (contains controller secret, never exposed).
    for old in sorted(STATE.glob('backup-*'))[:-7]: shutil.rmtree(old)


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('job',choices=['definitions','packages']); job=parser.parse_args().job
    if os.geteuid()!=0: raise SystemExit('Root maintenance job required')
    os.umask(0o077)
    with (STATE/'maintenance.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        path=STATE/(job+'.json')
        record=json.loads(path.read_text()) if path.exists() else {}
        record.update(last_attempt=time.time(),last_result='running')
        def save():
            temporary=path.with_suffix('.tmp'); temporary.write_text(json.dumps(record)+'\n')
            temporary.chmod(0o640); os.chown(temporary,0,pwd.getpwnam('wwcx-mail-gateway').pw_gid); temporary.replace(path)
        save()
        try:
            globals()[job]()
            record.update(last_success=time.time(),last_result='success',versions=versions()); save()
        except Exception as error:
            record.update(last_result='failed',error_type=type(error).__name__); save()
            print(json.dumps({'job':job,'result':'failed','error_type':type(error).__name__})); raise SystemExit(1)
        print(json.dumps({'job':job,'result':'success','last_success':record['last_success']}))

if __name__=='__main__': main()
