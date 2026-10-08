#!/usr/bin/env python3
"""Validate disposable historical MX rollback candidates; never modify public DNS."""
import json,subprocess,tempfile,hashlib,datetime
from pathlib import Path
root=Path(__file__).resolve().parents[2]
inventory=json.loads((root/'records/messaging/dns-inventories/mail-domain-dns-acceptance-20260804.json').read_text())['domains']
report={'contract':'wwcx.mail-dns-rollback-rehearsal.v1','checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'disposable zone files; no public DNS writes','provider_mutation_permissions_verified':False,'legacy_delivery_verified':False,'domains':{}}
def mx(domain):
 r=subprocess.run(['dig','+time=3','+tries=1','+short',domain,'MX'],capture_output=True,text=True,check=True)
 lines=sorted(x.strip() for x in r.stdout.splitlines() if x.strip())
 if not lines or not all(len(x.split())==2 and x.split()[0].isdigit() for x in lines):raise RuntimeError('Invalid MX response for '+domain)
 return lines
def zone(domain,records):
 return '$ORIGIN '+domain+'.\n$TTL 300\n@ IN SOA ns.invalid. hostmaster.invalid. (2026100801 60 60 3600 300)\n@ IN NS ns.invalid.\nproof IN TXT "preserve unrelated records"\n'+''.join('@ IN MX '+x.rstrip('.')+'.\n' for x in records)
def check(domain,text,path):
 path.write_text(text);subprocess.run(['named-checkzone',domain,str(path)],check=True,capture_output=True)
with tempfile.TemporaryDirectory(prefix='wwcx-mx-rehearsal-') as tmp:
 for domain,data in inventory.items():
  before=mx(domain)
  if before!=['10 mail.ww.cx.']:raise RuntimeError('Live MX differs from expected for '+domain)
  prior=data['mx']
  # Historical state is test input, never an assertion of working fallback delivery.
  path=Path(tmp)/(domain+'.zone');live=zone(domain,before);check(domain,live,path)
  rollback=zone(domain,prior);check(domain,rollback,path)
  assert 'proof IN TXT "preserve unrelated records"' in path.read_text()
  check(domain,live,path);assert path.read_text()==live
  after=mx(domain);assert before==after
  report['domains'][domain]={'live_mx_before':before,'historical_mx_test_input':prior,'rollback_zone_syntax':'passed','unrelated_record_preserved':True,'return_to_edge1_byte_equal':True,'live_mx_after':after,'live_dns_unchanged':True,'fallback_route_ready':False}
  if domain=='spiritcreekgardens.com':report['domains'][domain]['limitation']='Historical baseline has no MX; removing MX is not a viable fallback plan.'
  elif domain=='omegafx.com':report['domains'][domain]['limitation']='Historical cPanel MX conflicts with later PrivateEmail mailbox history; verify current provider route before use.'
report['result']='passed_isolated_only'
p=Path('/var/lib/wwcx-mail-room-reports/dns-rollback-rehearsal-20261008.json');p.write_text(json.dumps(report,indent=2)+'\n');p.chmod(0o600)
print(json.dumps({'result':report['result'],'domains_checked':len(report['domains']),'public_dns_unchanged':True,'production_rollback_verified':False}))
