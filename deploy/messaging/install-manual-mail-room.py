#!/usr/bin/env python3
"""Install on Edge1's existing private authenticated listener from a staged release."""
import argparse
import json
import os
from pathlib import Path
import pwd
import secrets
import shutil
import subprocess
from datetime import datetime, timezone


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--release', type=Path, required=True)
    release = parser.parse_args().release.resolve()
    if os.geteuid() != 0 or release.parent != Path('/opt/wwcx-email/releases') or not (release / 'server/mail_room_http.py').is_file():
        raise SystemExit('Root and an approved staged release are required')
    if release.stat().st_uid != 0 or release.stat().st_mode & 0o022:
        raise SystemExit('Release must be root-owned and not group/world writable')
    # Connector staging may inherit umask 0077. Source is public, config is separate.
    for path in [release, *release.rglob('*')]:
        if path.is_dir():
            path.chmod(0o755)
    nginx = Path('/etc/nginx/sites-enabled/edge1-private.conf').resolve()
    original = nginx.read_text()
    if 'listen 10.77.0.1:443 ssl;' not in original or 'location = /_edge1_status_session_check' not in original:
        raise SystemExit('Expected private session boundary missing')
    backup = Path('/var/backups/wwcx-email-recovery') / ('manual-mail-room-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    backup.mkdir(mode=0o700, parents=True)
    navigation = Path('/var/www/edge1-status/operator-shell/navigation.json')
    portal = Path('/var/www/edge1-status/index.html')
    contacts = Path('/var/www/contacts/app.js')
    for path, name in [(nginx, 'nginx-private.conf'), (navigation, 'navigation.json'), (portal, 'operations-index.html')]:
        shutil.copy2(path, backup / name)
    if contacts.exists():
        shutil.copy2(contacts, backup / 'contacts-app.js')
        source = contacts.read_text()
        # Apply only the small startup-query change to the live Contacts UI.
        if 'new URLSearchParams(window.location.search).get("q")' not in source:
            if '  query: "",' not in source or 'const $ = (selector) => document.querySelector(selector);' not in source:
                raise SystemExit('Contacts startup differs; no blind overwrite is allowed')
            source = source.replace('  query: "",', '  query: (new URLSearchParams(window.location.search).get("q") || "").slice(0, 200),', 1)
            source = source.replace('const $ = (selector) => document.querySelector(selector);', 'const $ = (selector) => document.querySelector(selector);\nif (state.query) { const searchInput = $("#search"); if (searchInput) searchInput.value = state.query; }', 1)
            contacts.write_text(source)
    env = Path('/etc/wwcx/mail-room.env')
    if env.exists():
        key = dict(line.split('=', 1) for line in env.read_text().splitlines() if '=' in line)['WWCX_MAIL_ROOM_PROXY_KEY']
    else:
        key = secrets.token_hex(32)
        env.write_text('WWCX_MAIL_ROOM_PROXY_KEY=' + key + '\n')
        env.chmod(0o600)
    user = pwd.getpwnam('wwcx-mail-gateway')
    state = Path('/var/lib/wwcx-mail-room-drafts')
    state.mkdir(mode=0o700, exist_ok=True)
    os.chown(state, user.pw_uid, user.pw_gid)
    dest = Path('/var/www/mail-room')
    if dest.exists():
        shutil.copytree(dest, backup / 'web')
    shutil.copytree(release / 'src/web/mail-room', dest, dirs_exist_ok=True)
    for path in dest.iterdir():
        path.chmod(0o644)
    dest.chmod(0o755)
    unit = Path('/etc/systemd/system/wwcx-mail-room.service')
    if unit.exists():
        shutil.copy2(unit, backup / 'service')
    unit.write_text(f'''[Unit]
Description=Edge1 authenticated manual Mail Room bridge
After=network.target wwcx-outbound-mail-gateway.service
[Service]
User=wwcx-mail-gateway
Group=wwcx-mail-gateway
WorkingDirectory={release}
EnvironmentFile=/etc/wwcx/mail-gateway.env
EnvironmentFile=/etc/wwcx/mail-room.env
EnvironmentFile=-/etc/wwcx/mail-room-ava.env
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart=/usr/bin/python3 -B -m server.mail_room_http --database {state}/drafts.sqlite3
Restart=on-failure
RestartSec=3
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
PrivateDevices=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths={state}
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
[Install]
WantedBy=multi-user.target
''')
    include = Path('/etc/nginx/snippets/wwcx-manual-mail-room.conf')
    include.parent.mkdir(parents=True, exist_ok=True)
    if include.exists():
        shutil.copy2(include, backup / 'nginx-snippet')
    include.write_text('''# Session-authenticated private Mail Room; browser receives no signing key.
location ^~ /edge1-ops/mail-room/api/ {
    auth_request /_edge1_status_session_check;
    proxy_pass http://127.0.0.1:8117;
    proxy_set_header X-Mail-Room-Proxy-Key "''' + key + '''";
    proxy_set_header Host edge1.ww.cx;
    proxy_connect_timeout 5s;
    proxy_read_timeout 90s;
    client_max_body_size 150k;
    access_log off;
    add_header Cache-Control "no-store" always;
    add_header X-Content-Type-Options "nosniff" always;
}
location ^~ /edge1-ops/mail-room/ {
    set $edge1_return_to $request_uri;
    auth_request /_edge1_status_session_check;
    error_page 401 = @edge1_status_login;
    alias /var/www/mail-room/;
    index index.html;
    add_header Cache-Control "no-store" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "no-referrer" always;
    add_header X-Frame-Options "DENY" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'" always;
}
''')
    include.chmod(0o600)
    directive = '    include /etc/nginx/snippets/wwcx-manual-mail-room.conf;'
    if directive not in original:
        pos = original.rfind('}')
        nginx.write_text(original[:pos] + directive + '\n' + original[pos:])
    check = subprocess.run(['nginx', '-t'], capture_output=True, text=True)
    if check.returncode:
        nginx.write_text(original)
        raise SystemExit('nginx validation failed; main configuration restored')
    gateway_unit = Path('/etc/systemd/system/wwcx-outbound-mail-gateway.service')
    if gateway_unit.exists():
        shutil.copy2(gateway_unit, backup / 'outbound-mail-gateway.service')
        import re
        current = gateway_unit.read_text()
        updated = re.sub(r'/opt/wwcx-email/releases/[0-9a-f]{40}', str(release), current)
        if updated != current:
            gateway_unit.write_text(updated)
    subprocess.run(['systemctl', 'daemon-reload'], check=True)
    subprocess.run(['systemctl', 'enable', '--now', 'wwcx-mail-room'], check=True)
    subprocess.run(['systemctl', 'restart', 'wwcx-outbound-mail-gateway'], check=True)
    subprocess.run(['systemctl', 'restart', 'wwcx-mail-room'], check=True)
    subprocess.run(['systemctl', 'reload', 'nginx'], check=True)
    if 'WWCX_MAIL_SECURITY_REQUIRED=true' not in Path('/etc/wwcx/mail-gateway.env').read_text().splitlines():
        scan_unit = Path('/etc/systemd/system/wwcx-mail-room-attachment-scan.service')
        scan_timer = Path('/etc/systemd/system/wwcx-mail-room-attachment-scan.timer')
        scan_unit.write_text(f"""[Unit]
    Description=Private native mail attachment inventory and scanner
    [Service]
    Type=oneshot
    User=wwcx-mail-gateway
    Group=wwcx-mail-gateway
    WorkingDirectory={release}
    ExecStart=/usr/bin/python3 -B {release}/tools/messaging/mail_room_attachment_scan.py --archive-root /var/lib/wwcx-mail-gateway/inbound --database {state}/drafts.sqlite3
    UMask=0077
    NoNewPrivileges=true
    PrivateTmp=true
    ProtectSystem=strict
    ProtectHome=true
    ReadWritePaths={state}
    MemoryMax=1G
    CPUQuota=35%
    TimeoutStartSec=600
    """)
        scan_timer.write_text("""[Unit]
    Description=Periodic private mail attachment checks
    [Timer]
    OnBootSec=2min
    OnUnitActiveSec=5min
    Persistent=true
    [Install]
    WantedBy=timers.target
    """)
        subprocess.run(['systemctl', 'daemon-reload'], check=True)
        subprocess.run(['systemctl', 'enable', '--now', 'wwcx-mail-room-attachment-scan.timer'], check=True)
        subprocess.run(['systemctl', 'start', '--no-block', 'wwcx-mail-room-attachment-scan'], check=True)
    report_unit = Path('/etc/systemd/system/wwcx-mail-room-daily-summary.service')
    report_timer = Path('/etc/systemd/system/wwcx-mail-room-daily-summary.timer')
    for path in [report_unit, report_timer]:
        if path.exists(): shutil.copy2(path, backup / path.name)
    report_unit.write_text(f"""[Unit]
Description=Aggregate-only Edge1 daily activity summary
[Service]
Type=oneshot
User=root
WorkingDirectory={release}
ExecStart=/usr/bin/python3 -B {release}/tools/messaging/mail_room_daily_summary.py
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/wwcx-mail-room-reports
""")
    report_timer.write_text("""[Unit]
Description=Refresh current-day summary and retain completed day reports
[Timer]
OnBootSec=2min
OnCalendar=*-*-* *:0/5:00 America/Regina
Persistent=true
[Install]
WantedBy=timers.target
""")
    reports = Path('/var/lib/wwcx-mail-room-reports')
    reports.mkdir(mode=0o750, exist_ok=True)
    os.chown(reports, 0, user.pw_gid)
    subprocess.run(['systemctl', 'daemon-reload'], check=True)
    subprocess.run(['systemctl', 'enable', '--now', 'wwcx-mail-room-daily-summary.timer'], check=True)
    subprocess.run(['systemctl', 'start', 'wwcx-mail-room-daily-summary'], check=True)
    registry = json.loads(navigation.read_text())
    module = next(m for m in registry['modules'] if m['id'] == 'mail-room')
    module.update(browser_route='/edge1-ops/mail-room/', runtime_route='/edge1-ops/mail-room/', availability='accepted_live', authorization='existing_route_policy', description='Browse mail, read threads, and save or prepare drafts. Provider commissioning pending; sending disabled.', palette=True, toolbox=True, evidence_status='private_authenticated_route_installed', menu_visibility='primary')
    navigation.write_text(json.dumps(registry, indent=2) + '\n')
    page = portal.read_text()
    if 'href="/edge1-ops/mail-room/"' not in page:
        marker = '<a class="card module-card" href="/edge1-ops/status/ava/"'
        line = next((line for line in page.splitlines() if marker in line), None)
        if line:
            page = page.replace(line, line + '\n<a class="card module-card" href="/edge1-ops/mail-room/"><h3>Mail Room</h3><small>Browse correspondence, read threads, and prepare your own drafts alongside AVA.</small></a>', 1)
            portal.write_text(page)
    print(json.dumps({'installed': True, 'url': 'https://edge1.ww.cx/edge1-ops/mail-room/', 'backup': str(backup), 'send_enabled': False}))


if __name__ == '__main__':
    main()
