#!/usr/bin/env python3
"""Capture current DNS mail-routing observations without changing records."""
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from tools.messaging.mail_room_readiness import DOMAINS,ROOT,save


def main():
    if os.geteuid()!=0:raise SystemExit('Root required for private baseline storage')
    os.umask(0o077);observed={}
    for domain in DOMAINS:
        observed[domain]={}
        for label,name,kind in [('ns',domain,'NS'),('soa',domain,'SOA'),('mx',domain,'MX'),('txt',domain,'TXT'),('dmarc','_dmarc.'+domain,'TXT')]:
            try:
                result=subprocess.run(['dig','+time=3','+tries=1','+noall','+answer',name,kind],capture_output=True,text=True,timeout=5)
                observed[domain][label]={'query_succeeded':result.returncode==0,'answers':result.stdout.splitlines() if result.returncode==0 else []}
            except (OSError,subprocess.TimeoutExpired):observed[domain][label]={'query_succeeded':False,'answers':[]}
    report={'captured_at':datetime.now(timezone.utc).isoformat(),'source':'Edge1 configured resolver; external authoritative/propagation verification still required',
            'domains':observed,'dns_modified':False,'commissioning_verified':False}
    save(report,ROOT/'dns-baseline.json')
    backup=Path('/var/backups/wwcx-email-recovery')/('dns-baseline-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.json')
    backup.write_text(json.dumps(report,indent=2)+'\n');backup.chmod(0o600)
    print(json.dumps({'dns_baseline_captured':True,'domains':len(observed),'dns_modified':False,'public_propagation_verified':False}))

if __name__=='__main__':main()
