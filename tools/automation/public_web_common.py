#!/usr/bin/env python3
from __future__ import annotations
import html.parser, io, json, time, urllib.error, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from pathlib import Path
UA='WWCX-Edge1-Website-Monitor/1.0 (+https://ww.cx/)'
MAX_BYTES=2*1024*1024

def fetch(url, *, max_bytes=MAX_BYTES, timeout=12, retries=1):
    last=None
    for attempt in range(max(0,retries)+1):
        req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'text/html,application/xml,text/xml,text/plain,*/*;q=0.1'})
        try:
            with urllib.request.urlopen(req,timeout=timeout) as r:
                raw=r.read(max_bytes+1); truncated=len(raw)>max_bytes; raw=raw[:max_bytes]
                return {'ok':200<=r.status<400,'status':r.status,'url':r.geturl(),'content_type':r.headers.get_content_type(),'bytes':len(raw),'truncated':truncated,'body':raw}
        except urllib.error.HTTPError as e:
            last={'ok':False,'status':e.code,'url':e.geturl(),'content_type':e.headers.get_content_type() if e.headers else None,'bytes':0,'truncated':False,'body':b'','error':'HTTPError'}
            if e.code not in {429,500,502,503,504} or attempt>=retries:return last
        except Exception as e:
            last={'ok':False,'status':None,'url':url,'content_type':None,'bytes':0,'truncated':False,'body':b'','error':type(e).__name__}
            if attempt>=retries:return last
        time.sleep(0.25*(attempt+1))
    return last

def public(result): return {k:v for k,v in result.items() if k!='body'}

def decode(result):
    raw=result.get('body') or b''
    try:return raw.decode('utf-8')
    except UnicodeDecodeError:return raw.decode('utf-8','replace')

class MetaParser(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True); self.title_parts=[]; self.in_title=False; self.meta={}; self.links=[]; self.jsonld=0
    def handle_starttag(self,tag,attrs):
        a={str(k).lower():v for k,v in attrs if k}
        if tag.lower()=='title': self.in_title=True
        elif tag.lower()=='meta':
            key=(a.get('name') or a.get('property') or '').lower(); val=a.get('content') or ''
            if key:self.meta.setdefault(key,val.strip())
        elif tag.lower()=='link': self.links.append({k:(v or '') for k,v in a.items()})
        elif tag.lower()=='script' and (a.get('type') or '').lower()=='application/ld+json': self.jsonld+=1
    def handle_endtag(self,tag):
        if tag.lower()=='title': self.in_title=False
    def handle_data(self,data):
        if self.in_title:self.title_parts.append(data)
    def result(self):
        canon=next((x.get('href','') for x in self.links if 'canonical' in (x.get('rel','').lower().split())), '')
        fav=next((x.get('href','') for x in self.links if 'icon' in x.get('rel','').lower()), '')
        return {'title':' '.join(' '.join(self.title_parts).split())[:300],'description':self.meta.get('description','')[:500],'robots':self.meta.get('robots','')[:300],'canonical':canon[:1000],'favicon':fav[:1000],'og_title':self.meta.get('og:title','')[:300],'og_description':self.meta.get('og:description','')[:500],'og_image':self.meta.get('og:image','')[:1000],'jsonld_blocks':self.jsonld}

def parse_html(text):
    p=MetaParser()
    try:p.feed(text)
    except Exception:pass
    return p.result()

def _locs(xml_bytes):
    try:root=ET.fromstring(xml_bytes)
    except ET.ParseError:return [],None
    tag=root.tag.rsplit('}',1)[-1].lower(); result=[]
    for el in root.iter():
        if el.tag.rsplit('}',1)[-1].lower()=='loc' and el.text:result.append(el.text.strip())
    return result,tag

def sitemap_urls(start_url,domain,max_urls=100,max_maps=20):
    queue=[start_url]; seen_maps=set(); urls=[]
    while queue and len(seen_maps)<max_maps and len(urls)<max_urls:
        current=queue.pop(0)
        if current in seen_maps:continue
        seen_maps.add(current); r=fetch(current,max_bytes=4*1024*1024)
        if not r['ok']:continue
        locs,kind=_locs(r['body'])
        for loc in locs:
            try:u=urllib.parse.urlparse(loc); host=(u.hostname or '').lower()
            except Exception:continue
            if host not in {domain,'www.'+domain}:continue
            if kind=='sitemapindex':
                if loc not in seen_maps:queue.append(loc)
            elif kind=='urlset' and loc not in urls:
                urls.append(loc)
                if len(urls)>=max_urls:break
    return urls,sorted(seen_maps)

def load_sites(path):
    data=json.loads(Path(path).read_text()); return data.get('sites',[])
