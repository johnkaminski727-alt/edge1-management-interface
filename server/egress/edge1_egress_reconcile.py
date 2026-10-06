from __future__ import annotations
import json,os,subprocess,time,grp
from pathlib import Path
from .edge1_egress_registry import init_db,list_services
DB=Path('/var/lib/edge1-egress/egress.sqlite3'); STATE=Path('/var/lib/edge1-egress/status.json'); POLICY=Path('/var/lib/edge1-egress/policy.json')
NS='eg-us-a'; ROOTV='egr-usa-r'; NSV='egr-usa-n'; WG='wg-us-a'; ROOTIP='169.254.101.1'; NSIP='169.254.101.2'; ENDPOINT='149.40.51.231'; CONF='/etc/wireguard/wg-proton-us.conf'

def run(*args,check=True,capture=False):
 return subprocess.run(args,check=check,text=True,stdout=subprocess.PIPE if capture else None,stderr=subprocess.PIPE if capture else None)
def sh(s,check=True,capture=False):return subprocess.run(['/bin/bash','-lc',s],check=check,text=True,stdout=subprocess.PIPE if capture else None,stderr=subprocess.PIPE if capture else None)
def exists_ns():return NS in (run('ip','netns','list',capture=True).stdout or '')
def write_json(p,obj):
 t=p.with_suffix('.tmp');t.write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n');os.chown(t,0,grp.getgrnam('wwadmin').gr_gid);os.chmod(t,0o640);os.replace(t,p)

def setup_root_tables():
 # Preserve learned destination-set elements across periodic reconciliation.
 if sh('nft list table inet edge1_egress >/dev/null 2>&1',check=False).returncode!=0:
  init='''
add table inet edge1_egress
add set inet edge1_egress us4 { type ipv4_addr; flags timeout; timeout 6h; }
add chain inet edge1_egress prerouting { type filter hook prerouting priority mangle; policy accept; }
'''
  subprocess.run(['nft','-f','-'],input=init,text=True,check=True)
 else:
  sh('nft flush chain inet edge1_egress prerouting')
 rules='''
add rule inet edge1_egress prerouting iifname "wg0" ip daddr { 10.0.0.0/8, 127.0.0.0/8, 169.254.0.0/16, 172.16.0.0/12, 192.168.0.0/16 } meta mark set 0 ct mark set 0 return
add rule inet edge1_egress prerouting iifname "wg0" ct mark 0x101 meta mark set ct mark
add rule inet edge1_egress prerouting iifname "wg0" ip daddr @us4 ct mark set 0x101 meta mark set 0x101
'''
 subprocess.run(['nft','-f','-'],input=rules,text=True,check=True)
 if sh('nft list table ip edge1_egress_transport >/dev/null 2>&1',check=False).returncode!=0:
  transport='''
add table ip edge1_egress_transport
add chain ip edge1_egress_transport postrouting { type nat hook postrouting priority srcnat; policy accept; }
add rule ip edge1_egress_transport postrouting ip saddr 169.254.101.0/30 oifname "ens3" masquerade
'''
  subprocess.run(['nft','-f','-'],input=transport,text=True,check=True)
 sh("ip rule del pref 10101 2>/dev/null || true")
 run('ip','rule','add','pref','10101','fwmark','0x101/0xfff','lookup','52101')
 sh('ip route flush table 52101 2>/dev/null || true')
 run('ip','route','add','unreachable','default','metric','32767','table','52101')
 run('ip','route','add','default','via',NSIP,'dev',ROOTV,'onlink','metric','10','table','52101')

def setup_namespace():
 # old host-scoped test interface must not coexist with provider's repeated 10.2.0.2 address
 sh('systemctl stop wg-quick@wg-proton-us.service >/dev/null 2>&1 || true')
 sh('ip link del wg-proton-us 2>/dev/null || true')
 if not exists_ns():
  run('ip','netns','add',NS)
  run('ip','link','add',ROOTV,'type','veth','peer','name',NSV)
  run('ip','link','set',NSV,'netns',NS)
 else:
  # recreate veth if namespace survived without root side
  if sh(f'ip link show {ROOTV} >/dev/null 2>&1',check=False).returncode!=0:
   run('ip','link','add',ROOTV,'type','veth','peer','name',NSV)
   run('ip','link','set',NSV,'netns',NS)
 sh(f'ip addr replace {ROOTIP}/30 dev {ROOTV}');run('ip','link','set',ROOTV,'up')
 sh(f'ip netns exec {NS} ip link set lo up')
 sh(f'ip netns exec {NS} ip addr replace {NSIP}/30 dev {NSV}')
 sh(f'ip netns exec {NS} ip link set {NSV} up')
 sh(f'ip netns exec {NS} ip route replace {ENDPOINT}/32 via {ROOTIP} dev {NSV}')
 sh(f'ip netns exec {NS} ip route replace 10.77.0.0/24 via {ROOTIP} dev {NSV}')
 sh(f'ip netns exec {NS} sysctl -q -w net.ipv4.ip_forward=1')
 created=False
 if sh(f'ip netns exec {NS} ip link show {WG} >/dev/null 2>&1',check=False).returncode!=0:
  run('ip','netns','exec',NS,'ip','link','add',WG,'type','wireguard');created=True
 if created:
  tmp=Path('/run/edge1-egress-us.strip');tmp.parent.mkdir(parents=True,exist_ok=True)
  data=run('wg-quick','strip',CONF,capture=True).stdout;tmp.write_text(data);os.chmod(tmp,0o600)
  run('ip','netns','exec',NS,'wg','setconf',WG,str(tmp));run('ip','netns','exec',NS,'wg','set',WG,'listen-port','51831')
 sh(f'ip netns exec {NS} ip addr replace 10.2.0.2/32 dev {WG}')
 sh(f'ip netns exec {NS} ip link set mtu 1420 up dev {WG}')
 sh(f'ip netns exec {NS} ip route replace default dev {WG} metric 10')
 nsnft=f'''
table inet edge1_egress_ns {{
 chain input {{
  type filter hook input priority 0; policy drop;
  iifname "lo" accept
  ct state established,related accept
  ip protocol icmp accept
  iifname "{NSV}" ip saddr {ENDPOINT} udp sport 51820 accept
 }}
 chain forward {{
  type filter hook forward priority 0; policy drop;
  iifname "{NSV}" oifname "{WG}" ip saddr 10.77.0.0/24 accept
  iifname "{WG}" oifname "{NSV}" ct state established,related accept
 }}
}}
table ip edge1_egress_ns_nat {{
 chain postrouting {{
  type nat hook postrouting priority srcnat; policy accept;
  oifname "{WG}" ip saddr 10.77.0.0/24 masquerade
 }}
}}
'''
 sh(f'ip netns exec {NS} nft list table inet edge1_egress_ns >/dev/null 2>&1 && ip netns exec {NS} nft delete table inet edge1_egress_ns || true')
 sh(f'ip netns exec {NS} nft list table ip edge1_egress_ns_nat >/dev/null 2>&1 && ip netns exec {NS} nft delete table ip edge1_egress_ns_nat || true')
 subprocess.run(['ip','netns','exec',NS,'nft','-f','-'],input=nsnft,text=True,check=True)

def ensure_ufw():
 out=sh('ufw status',capture=True).stdout
 if 'Edge1 selected US egress' not in out:sh("ufw route allow in on wg0 out on egr-usa-r from 10.77.0.0/24 comment 'Edge1 selected US egress'")
 if 'Edge1 US egress transport' not in out:sh("ufw route allow in on egr-usa-r out on ens3 from 169.254.101.2 comment 'Edge1 US egress transport'")

def status():
 hs=0
 for _ in range(6):
  try:
   s=sh(f'ip netns exec {NS} wg show {WG} latest-handshakes',capture=True).stdout.strip().split()
   if s:hs=int(s[-1])
  except:pass
  now=int(time.time());age=(now-hs if hs else None)
  if hs and age<180:break
  time.sleep(1)
 now=int(time.time());age=(now-hs if hs else None);healthy=bool(hs and age<180)
 ip='';country=''
 if healthy:
  try:ip=sh(f"ip netns exec {NS} curl -4fsS --max-time 8 https://api.ipify.org",capture=True).stdout.strip()
  except:pass
  try:country=sh(f"ip netns exec {NS} curl -4fsS --max-time 8 https://ipinfo.io/country",capture=True).stdout.strip()
  except:pass
 return {'schema':'wwcx.edge1-egress-status.v1','updated_at':int(time.time()),'default':'direct','leak_policy':'fail_closed','gateways':[
  {'id':'direct','country':'direct','state':'active','healthy':True,'interface':'ens3'},
  {'id':'us-primary','pool':'us','profile':'US-FREE#122','state':'active' if healthy else 'degraded','healthy':healthy,'handshake_age_seconds':age,'egress_ip':ip,'observed_country':country,'namespace':NS},
  {'id':'us-secondary','pool':'us','profile':'US-FREE#26','state':'staged','healthy':False},
  {'id':'ca-primary','pool':'ca','profile':'CA-FREE#20','state':'staged','healthy':False},
  {'id':'mx-primary','pool':'mx','profile':'MX-FREE#2','state':'secret_pending','healthy':False}],
  'private_exclusions':['10.0.0.0/8','10.77.0.0/24','127.0.0.0/8','169.254.0.0/16','172.16.0.0/12','192.168.0.0/16']}

def export_policy():
 write_json(POLICY,{'schema':'wwcx.edge1-egress-policy.v1','services':list_services(DB)})
def main():
 DB.parent.mkdir(parents=True,exist_ok=True);init_db(DB);setup_namespace();setup_root_tables();ensure_ufw();export_policy();time.sleep(2);write_json(STATE,status())
if __name__=='__main__':main()
