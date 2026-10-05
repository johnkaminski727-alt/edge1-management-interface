#!/usr/bin/env python3
"""Install explicit update jobs for the private mail scanner and packaged rules."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import subprocess
import sys


def main():
    p=argparse.ArgumentParser();p.add_argument('--release',type=Path,required=True);release=p.parse_args().release.resolve()
    if os.geteuid()!=0 or release.parent!=Path('/opt/wwcx-email/releases') or release.stat().st_uid!=0 or release.stat().st_mode & 0o022: raise SystemExit('Root-owned immutable release required')
    os.umask(0o077)
    backup=Path('/var/backups/wwcx-email-recovery')/('mail-updates-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'));backup.mkdir(mode=0o700)
    fresh=Path('/etc/clamav/freshclam.conf');shutil.copy2(fresh,backup/'freshclam.conf')
    content=re.sub(r'^NotifyClamd .*$', 'NotifyClamd /etc/clamav/wwcx-mail-clamd.conf', fresh.read_text(), flags=re.M)
    if not re.search(r'^NotifyClamd ',content,re.M):content+='\nNotifyClamd /etc/clamav/wwcx-mail-clamd.conf\n'
    fresh.write_text(content)
    clamconf=Path('/etc/clamav/wwcx-mail-clamd.conf');shutil.copy2(clamconf,backup/clamconf.name)
    config=clamconf.read_text()
    if not re.search(r'^ConcurrentDatabaseReload ',config,re.M):
        clamconf.write_text(config+'\nConcurrentDatabaseReload no\n');clamconf.chmod(0o644)
        subprocess.run(['systemctl','restart','wwcx-mail-clamd'],check=True)
    group=pwd.getpwnam('wwcx-mail-gateway').pw_gid
    state=Path('/var/lib/wwcx-mail-updates');state.mkdir(exist_ok=True);state.chmod(0o750);os.chown(state,0,group)
    # Stop the distributor's daemon before the first hourly job to avoid lock contention.
    subprocess.run(['systemctl','disable','--now','clamav-freshclam.service'],check=True)
    # The package postinstall cannot restart a competing daemon.
    subprocess.run(['systemctl','mask','clamav-freshclam.service'],check=True)
    for job,calendar in [('definitions','*-*-* *:10:00 UTC'),('packages','*-*-* 09:15:00 UTC')]:
        Path('/etc/systemd/system/wwcx-mail-update-'+job+'.service').write_text(f'''[Unit]
Description=Private mail {job} update and acceptance probes
Wants=network-online.target
After=network-online.target wwcx-mail-clamd.service
[Service]
Type=oneshot
WorkingDirectory={release}
ExecStart=/usr/bin/python3 -B {release}/tools/messaging/mail_security_update.py {job}
Environment=PYTHONDONTWRITEBYTECODE=1
UMask=0077
PrivateTmp=true
ProtectHome=true
TimeoutStartSec=3600
''')
        Path('/etc/systemd/system/wwcx-mail-update-'+job+'.timer').write_text(f'''[Unit]
Description=Scheduled private mail {job} updates
[Timer]
OnCalendar={calendar}
Persistent=true
AccuracySec=1min
[Install]
WantedBy=timers.target
''')
    # Existing installer preserves the authenticated portal and current draft stores.
    subprocess.run([sys.executable,str(release/'deploy/messaging/install-manual-mail-room.py'),'--release',str(release)],check=True)
    unit=Path('/etc/systemd/system/wwcx-mail-security-scan.service')
    shutil.copy2(unit,backup/unit.name)
    unit.write_text(re.sub(r'/opt/wwcx-email/releases/[0-9a-f]{40}',str(release),unit.read_text()))
    subprocess.run(['systemctl','daemon-reload'],check=True)
    subprocess.run(['systemctl','enable','--now','wwcx-mail-update-definitions.timer','wwcx-mail-update-packages.timer'],check=True)
    subprocess.run(['systemctl','start','--no-block','wwcx-mail-update-definitions.service'],check=True)
    print(json.dumps({'installed':True,'backup':str(backup),'definitions':'hourly :10 UTC','packages':'03:15 America/Regina','sending_enabled':False}))

if __name__=='__main__':main()
