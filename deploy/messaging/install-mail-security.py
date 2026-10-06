#!/usr/bin/env python3
"""Install private shared intake screening without enabling delivery or public SMTP."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import pwd
import re
import secrets
import shutil
import sqlite3
import subprocess
import sys


def main():
    p=argparse.ArgumentParser();p.add_argument('--release',type=Path,required=True);release=p.parse_args().release.resolve()
    if os.geteuid()!=0 or release.parent!=Path('/opt/wwcx-email/releases') or release.stat().st_uid!=0 or release.stat().st_mode & 0o022: raise SystemExit('Approved root-owned release required')
    sys.path.insert(0,str(release))
    from server.mail_room_security import SecurityStore, DEFAULT_POLICY
    if not all(shutil.which(c) for c in ['rspamd','redis-server','clamd','clamdscan']): raise SystemExit('Rspamd, Redis and ClamAV daemon packages required')
    os.umask(0o077)
    backup=Path('/var/backups/wwcx-email-recovery')/('mail-security-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'));backup.mkdir(mode=0o700,parents=True)
    paths=['/etc/postfix/master.cf','/etc/wwcx/mail-gateway.env','/etc/systemd/system/wwcx-mail-room.service','/etc/systemd/system/wwcx-outbound-mail-gateway.service']
    for file in paths:
        path=Path(file)
        if path.exists():shutil.copy2(path,backup/path.name)
    for directory in ['/etc/rspamd/local.d','/etc/rspamd/override.d']:
        if Path(directory).exists():shutil.copytree(directory,backup/Path(directory).name)
    for file in ['/var/lib/wwcx-mail-room/correspondence.sqlite3','/var/lib/wwcx-mail-room-drafts/drafts.sqlite3','/var/lib/wwcx-mail-security/security.sqlite3']:
        path=Path(file)
        if path.is_file():
            with sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True) as source, sqlite3.connect(backup/path.parent.name) as destination:source.backup(destination)
    user=pwd.getpwnam('wwcx-mail-gateway');state=Path('/var/lib/wwcx-mail-security');state.mkdir(mode=0o700,exist_ok=True);state.chmod(0o700);os.chown(state,user.pw_uid,user.pw_gid)
    security=SecurityStore(state/'security.sqlite3');os.chown(security.path,user.pw_uid,user.pw_gid)
    policy=Path('/etc/wwcx/mail-security-policy.json')
    if not policy.exists():policy.write_text(json.dumps(DEFAULT_POLICY,indent=2)+'\n')
    policy.chmod(0o640);os.chown(policy,0,user.pw_gid)
    env=Path('/etc/wwcx/mail-security.env')
    if env.exists():password=dict(line.split('=',1) for line in env.read_text().splitlines() if '=' in line)['WWCX_RSPAMD_CONTROLLER_PASSWORD']
    else:
        password=secrets.token_hex(32);env.write_text('WWCX_RSPAMD_CONTROLLER_PASSWORD='+password+'\n');env.chmod(0o600)
    rspamd_user=pwd.getpwnam('_rspamd');local=Path('/etc/rspamd/local.d');local.mkdir(exist_ok=True)
    configs={
      'worker-normal.inc':'bind_socket = "127.0.0.1:11333";\ncount = 1;\n',
      'worker-controller.inc':'bind_socket = "127.0.0.1:11334";\npassword = "'+password+'";\nenable_password = "'+password+'";\n',
      'worker-proxy.inc':'enabled = false;\n',
      'redis.conf':'servers = "127.0.0.1:6379";\n',
      'classifier-bayes.conf':'backend = "redis";\nnew_schema = true;\nmin_learns = 20;\nautolearn = false;\n',
      'fuzzy_check.conf':'enabled = false;\n',
      'gpt.conf':'enabled = false;\n',
      'url_redirector.conf':'enabled = false;\n',
      'history_redis.conf':'enabled = false;\n',
      'actions.conf':'reject = 15;\nadd_header = 6;\ngreylist = null;\nrewrite_subject = null;\n',
      'antivirus.conf':'enabled = false;\n',
      'logging.inc':'level = "warning";\n',
    }
    for name,content in configs.items():
        target=local/name;target.write_text(content);target.chmod(0o640);os.chown(target,0,rspamd_user.pw_gid)
    clamconf=Path('/etc/clamav/wwcx-mail-clamd.conf')
    clamconf.write_text('''User clamav
DatabaseDirectory /var/lib/clamav
LocalSocket /run/wwcx-mail-clamd/scan.sock
LocalSocketGroup wwcx-mail-gateway
LocalSocketMode 660
FixStaleSocket yes
Foreground yes
LogTime yes
MaxThreads 2
StreamMaxLength 30M
MaxFileSize 25M
MaxScanSize 30M
MaxRecursion 10
MaxFiles 1000
MaxScanTime 60000
AlertExceedsMax yes
AlertEncrypted yes
SelfCheck 600
ConcurrentDatabaseReload no
''');clamconf.chmod(0o644)
    apparmor=Path('/etc/apparmor.d/local/usr.sbin.clamd')
    if Path('/etc/apparmor.d/usr.sbin.clamd').is_file():
        if apparmor.exists():shutil.copy2(apparmor,backup/'clamd-apparmor-local')
        original=apparmor.read_text() if apparmor.exists() else ''
        marker='# WW.CX private mail scanner'
        if marker not in original:
            apparmor.write_text(original+'\n'+marker+'\n/etc/clamav/wwcx-mail-clamd.conf r,\n/run/wwcx-mail-clamd/ rw,\n/run/wwcx-mail-clamd/scan.sock rw,\n')
        subprocess.run(['apparmor_parser','-r','/etc/apparmor.d/usr.sbin.clamd'],check=True)
    subprocess.run(['runuser','-u','clamav','--','/usr/sbin/clamd','--config-file='+str(clamconf),'--version'],check=True,stdout=subprocess.DEVNULL)
    Path('/etc/systemd/system/wwcx-mail-clamd.service').write_text('''[Unit]
Description=Private local mail malware scanner
After=clamav-freshclam.service
[Service]
Type=simple
User=clamav
Group=wwcx-mail-gateway
RuntimeDirectory=wwcx-mail-clamd
RuntimeDirectoryMode=0750
ExecStart=/usr/sbin/clamd --config-file=/etc/clamav/wwcx-mail-clamd.conf
Restart=on-failure
RestartSec=10
NoNewPrivileges=true
PrivateTmp=true
PrivateDevices=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/run/wwcx-mail-clamd
RestrictAddressFamilies=AF_UNIX
MemoryMax=1400M
CPUQuota=35%
[Install]
WantedBy=multi-user.target
''')
    subprocess.run(['rspamadm','configtest'],check=True,stdout=subprocess.DEVNULL)
    subprocess.run(['redis-cli','CONFIG','SET','maxmemory','64mb'],check=True,stdout=subprocess.DEVNULL)
    subprocess.run(['redis-cli','CONFIG','SET','maxmemory-policy','allkeys-lru'],check=True,stdout=subprocess.DEVNULL)
    subprocess.run(['redis-cli','CONFIG','REWRITE'],check=True,stdout=subprocess.DEVNULL)
    drop=Path('/etc/systemd/system/rspamd.service.d');drop.mkdir(exist_ok=True)
    (drop/'mail-security-limits.conf').write_text('[Service]\nMemoryMax=512M\nCPUQuota=35%\n')
    gateway_env=Path('/etc/wwcx/mail-gateway.env');content=gateway_env.read_text()
    content=re.sub(r'^WWCX_MAIL_SECURITY_(REQUIRED|DATABASE)=.*\n?','',content,flags=re.M)
    gateway_env.write_text(content.rstrip()+'\nWWCX_MAIL_SECURITY_REQUIRED=true\nWWCX_MAIL_SECURITY_DATABASE=/var/lib/wwcx-mail-security/security.sqlite3\n');gateway_env.chmod(0o600)
    # Invoke existing installer to preserve all current route and navigation behavior.
    subprocess.run([sys.executable,str(release/'deploy/messaging/install-manual-mail-room.py'),'--release',str(release)],check=True)
    for service,permission in [('wwcx-mail-room','ReadWritePaths'),('wwcx-outbound-mail-gateway','ReadOnlyPaths')]:
        folder=Path('/etc/systemd/system/'+service+'.service.d');folder.mkdir(exist_ok=True)
        (folder/'mail-security.conf').write_text('[Service]\n'+permission+'=/var/lib/wwcx-mail-security\n')
    master=Path('/etc/postfix/master.cf');current=master.read_text()
    pattern=r'/opt/wwcx-email/releases/[0-9a-f]{40}/tools/messaging/edge1_mail_gateway_archive.py'
    if len(re.findall(pattern,current))!=1:raise SystemExit('Expected single managed Postfix archive command')
    current=re.sub(pattern,str(release/'tools/messaging/edge1_mail_gateway_archive.py'),current)
    if '--client-ip' not in current:
        current=current.replace('--stdin --recipient','--stdin --client-ip ${client_address} --envelope-sender ${sender} --recipient',1)
    master.write_text(current)
    # The worker replaces the old advisory attachment-only timer.
    subprocess.run(['systemctl','disable','--now','wwcx-mail-room-attachment-scan.timer'],check=True)
    subprocess.run(['systemctl','stop','wwcx-mail-room-attachment-scan.service'],check=True)
    unit=Path('/etc/systemd/system/wwcx-mail-security-scan.service')
    unit.write_text(f'''[Unit]
Description=Unified private mail security release gate
After=rspamd.service redis-server.service wwcx-mail-clamd.service
[Service]
Type=oneshot
User=wwcx-mail-gateway
Group=wwcx-mail-gateway
WorkingDirectory={release}
EnvironmentFile=/etc/wwcx/mail-security.env
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart=/usr/bin/python3 -B {release}/tools/messaging/mail_room_security_scan.py
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
PrivateDevices=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/wwcx-mail-security /var/lib/wwcx-mail-room-drafts
MemoryMax=256M
CPUQuota=35%
TimeoutStartSec=600
''')
    Path('/etc/systemd/system/wwcx-mail-security-scan.timer').write_text('''[Unit]
Description=Inspect pending mail before inbox or AVA release
[Timer]
OnBootSec=1min
OnUnitActiveSec=1min
Persistent=true
[Install]
WantedBy=timers.target
''')
    subprocess.run(['systemctl','daemon-reload'],check=True)
    subprocess.run(['systemctl','enable','--now','rspamd','redis-server','wwcx-mail-clamd','wwcx-mail-security-scan.timer'],check=True)
    subprocess.run(['systemctl','restart','rspamd','wwcx-outbound-mail-gateway','wwcx-mail-room'],check=True)
    subprocess.run(['postfix','check'],check=True)
    subprocess.run(['systemctl','reload','postfix'],check=True)
    subprocess.run(['systemctl','start','--no-block','wwcx-mail-security-scan'],check=True)
    print(json.dumps({'installed':True,'security_gate_required':True,'backup':str(backup),'public_smtp_enabled':False,'sending_enabled':False,'provider_connected':False}))

if __name__=='__main__':main()
