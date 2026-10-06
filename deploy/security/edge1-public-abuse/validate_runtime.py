from pathlib import Path
import tempfile,subprocess,http.client,collections,json,shutil
root=Path(__file__).parent
with tempfile.TemporaryDirectory(prefix='edge1-public-abuse-test-') as temp:
 p=Path(temp);p.chmod(0o755);(p/'www').mkdir();(p/'www').chmod(0o755)
 token=p/'www/.well-known/acme-challenge';token.mkdir(parents=True);token.chmod(0o755);token.parent.chmod(0o755)
 (token/'probe').write_text('ACME_OK');(token/'probe').chmod(0o644)
 common=(root/'common.conf').read_text()
 for net in ['127.0.0.0/8','::1','10.77.0.0/24','89.126.248.191/32']: common=common.replace(net+' 1;',net+' 0;')
 server=(root/'public.conf').read_text().split('server {')[1].split('server {')[0]
 server=server.replace('listen 89.126.248.191:80 default_server;','listen 127.0.0.1:18991;\nlisten 127.0.0.1:18992;').replace('/var/www/edge1-acme',str(p/'www')).replace('/var/log/nginx/edge1-public-abuse.log',str(p/'abuse.log'))
 config='pid '+str(p/'nginx.pid')+'; error_log '+str(p/'error.log')+'; events {} http { '+common+' server {'+server+' }'
 (p/'nginx.conf').write_text(config)
 subprocess.run(['nginx','-t','-c',str(p/'nginx.conf')],check=True,capture_output=True)
 subprocess.run(['nginx','-c',str(p/'nginx.conf')],check=True)
 def req(path,port=18991):
  c=http.client.HTTPConnection('127.0.0.1',port,timeout=3);c.request('GET',path);r=c.getresponse();result=(r.status,r.getheader('Location'),r.getheader('Retry-After'),r.read().decode());c.close();return result
 try:
  first=req('/');print('FIRST',first[:3]);assert first[0:2]==(302,'https://www.ww.cx/'),first
  probes=collections.Counter(req('/admin/login')[0] for _ in range(12));print('PROBES',dict(probes));assert probes[429]>=6,probes
  burst=collections.Counter(req('/')[0] for _ in range(100));print('BURST',dict(burst));assert burst[429]>70,burst
  assert req('/',18992)[0]==429,'shared HTTP/HTTPS bucket bypass'
  acme=[req('/.well-known/acme-challenge/probe') for _ in range(20)];print('ACME',acme[0][:3]);assert all(x[0]==200 and x[3]=='ACME_OK' for x in acme)
  assert req('/')[2]=='60','Retry-After missing'
  print('PASS redirect, burst, shared bucket, Retry-After and ACME exemption')
 finally:subprocess.run(['nginx','-s','quit','-c',str(p/'nginx.conf')],check=True,capture_output=True)
 shutil.copyfile(p/'abuse.log',root/'isolated-abuse.log')
 (root/'isolated-test.json').write_text(json.dumps({'general_burst':dict(burst),'acme_exempt':True,'shared_bucket':True}))
