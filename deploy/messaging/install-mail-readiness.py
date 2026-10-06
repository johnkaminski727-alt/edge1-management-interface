#!/usr/bin/env python3
"""Deploy preparation views and aggregate monitoring; never change DNS or delivery."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


def main():
    p=argparse.ArgumentParser();p.add_argument('--release',type=Path,required=True);release=p.parse_args().release.resolve()
    if os.geteuid()!=0 or release.parent!=Path('/opt/wwcx-email/releases') or release.stat().st_uid!=0 or release.stat().st_mode & 0o022:raise SystemExit('Root-owned immutable release required')
    subprocess.run([sys.executable,str(release/'deploy/messaging/install-manual-mail-room.py'),'--release',str(release)],check=True)
    Path('/etc/systemd/system/wwcx-mail-readiness.service').write_text(f'''[Unit]
Description=Aggregate private mail readiness and operational health
[Service]
Type=oneshot
WorkingDirectory={release}
ExecStart=/usr/bin/python3 -B {release}/tools/messaging/mail_room_readiness.py
Environment=PYTHONDONTWRITEBYTECODE=1
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/wwcx-mail-room-reports
TimeoutStartSec=120
''')
    Path('/etc/systemd/system/wwcx-mail-readiness.timer').write_text('''[Unit]
Description=Refresh mail readiness and backlog warnings every five minutes
[Timer]
OnBootSec=1min
OnCalendar=*-*-* *:0/5:00 UTC
Persistent=true
[Install]
WantedBy=timers.target
''')
    subprocess.run(['systemctl','daemon-reload'],check=True)
    subprocess.run(['systemctl','enable','--now','wwcx-mail-readiness.timer'],check=True)
    subprocess.run(['systemctl','start','wwcx-mail-readiness.service'],check=True)
    print(json.dumps({'readiness_installed':True,'access':'admin_only','dns_modified':False,'sending_enabled':False}))

if __name__=='__main__':main()
