import struct,socket,tempfile,subprocess,json,collections
from pathlib import Path
def checksum(data):
 if len(data)%2: data+=b'\0'
 value=sum(struct.unpack('!%dH'%(len(data)//2),data))
 while value>>16: value=(value&65535)+(value>>16)
 return (~value)&65535
src=socket.inet_aton('192.0.2.10'); dst=socket.inet_aton('10.77.0.3')
def ip(proto,payload):
 h=struct.pack('!BBHHHBBH4s4s',0x45,0,20+len(payload),1,0,64,proto,0,src,dst)
 return h[:10]+struct.pack('!H',checksum(h))+h[12:]+payload
def tcp():
 h=struct.pack('!HHIIBBHHH',12345,443,1,0,0x60,2,8192,0,0)+b'\x02\x01\x00\x00'
 pseudo=src+dst+struct.pack('!BBH',0,6,len(h))
 h=h[:16]+struct.pack('!H',checksum(pseudo+h))+h[18:]
 return ip(6,h)
def udp():
 data=b'EDGE1_TUNING_CANARY'
 h=struct.pack('!HHHH',12346,44444,8+len(data),0)
 return ip(17,h+data)
with tempfile.TemporaryDirectory(prefix='edge1-suricata-probe-') as temp:
 root=Path(temp); pcap=root/'probe.pcap'
 with pcap.open('wb') as f:
  f.write(struct.pack('<IHHIIII',0xa1b2c3d4,2,4,0,0,65535,101))
  for n,packet in [(0,tcp()),(1,tcp()),(2,tcp()),(3,tcp()),(70,tcp()),(71,udp())]:
   f.write(struct.pack('<IIII',1800000000+n,0,len(packet),len(packet))); f.write(packet)
 production=Path('/opt/wwcx-suricata/current/var/lib/suricata/rules/suricata.rules').read_text()
 rule=next(line for line in production.splitlines() if 'sid:2200036;' in line)
 rules=root/'probe.rules'; rules.write_text(rule+'\n'+
  'alert udp $EXTERNAL_NET any -> $HOME_NET 44444 (msg:"EDGE1 offline harmless canary"; content:"EDGE1_TUNING_CANARY"; sid:9900001; rev:1;)\n')
 command=['/opt/wwcx-suricata/current/bin/suricata','-c','/etc/wwcx-suricata/suricata.yaml','-r',str(pcap),'-S',str(rules),'-l',str(root),'--runmode','single','-k','none']
 done=subprocess.run(command,capture_output=True,text=True,timeout=30)
 if done.returncode: raise RuntimeError(done.stdout+done.stderr)
 counts=collections.Counter()
 for line in (root/'eve.json').read_text().splitlines():
  event=json.loads(line)
  if event.get('event_type')=='alert': counts[event['alert']['signature_id']]+=1
 print('Offline alert counts:',dict(counts))
 assert counts[2200036]==2,counts
 assert counts[9900001]==1,counts
 print('PASS: first warning retained, repeats limited, warning resumes after 60 seconds, HOME_NET canary detected')
