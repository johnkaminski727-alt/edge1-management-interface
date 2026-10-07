#!/usr/bin/env python3
from __future__ import annotations
import json, urllib.request
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT))
from tools.automation.automation_common import utcnow, upsert_library_document
LIVE='https://ww.cx/api/catalog.php'; FALLBACK='https://ww.cx/assets/data/catalog.default.json'
STATUS=Path('/var/www/edge1-status/catalog-consistency/status.json'); LIB=Path('/var/lib/bigbird-ai-library/library.sqlite3')
FIELDS=('name','price','sku','product_type','image','stripe_url','collection','brand')
def fetch_json(url):
    req=urllib.request.Request(url,headers={'User-Agent':'WWCX-Catalog-Consistency/1.0','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=20) as r:
        if r.status!=200: raise RuntimeError(f'{url} HTTP {r.status}')
        return json.loads(r.read(4*1024*1024).decode('utf-8'))
def catalog(data): return data.get('catalog',data) if isinstance(data,dict) else {}
def index_products(items):
    out={}; dup=[]
    for p in items or []:
        if not isinstance(p,dict) or not p.get('id'): continue
        ident=str(p['id'])
        if ident in out: dup.append(ident)
        out[ident]=p
    return out,sorted(set(dup))
def compare(live_data,fallback_data):
    live=catalog(live_data); fallback=catalog(fallback_data); findings=[]
    li,ld=index_products(live.get('products')); fi,fd=index_products(fallback.get('products'))
    active={i:p for i,p in fi.items() if p.get('active') is not False}; inactive={i:p for i,p in fi.items() if p.get('active') is False}
    for ident in ld: findings.append({'kind':'duplicate_live_id','severity':'high','product_id':ident,'detail':'Duplicate product id in live API.'})
    for ident in fd: findings.append({'kind':'duplicate_fallback_id','severity':'high','product_id':ident,'detail':'Duplicate product id in fallback catalog.'})
    for ident in sorted(set(active)-set(li)): findings.append({'kind':'active_product_missing_live','severity':'high','product_id':ident,'detail':'Active fallback product is missing from live API.'})
    for ident in sorted(set(li)-set(active)): findings.append({'kind':'unexpected_live_product','severity':'high','product_id':ident,'detail':'Live API product is not active in fallback catalog.'})
    for ident in sorted(set(li)&set(inactive)): findings.append({'kind':'inactive_product_leaked_live','severity':'high','product_id':ident,'detail':'Inactive fallback product is exposed by live API.'})
    for ident in sorted(set(li)&set(active)):
        a,b=li[ident],active[ident]
        for field in FIELDS:
            # Stripe checkout URLs may be injected by the live catalog projection while
            # the fallback intentionally leaves them unset. An absent fallback value is
            # therefore not drift; an explicitly declared fallback URL must still match.
            if field == 'stripe_url' and b.get(field) in (None, ''):
                continue
            if a.get(field)!=b.get(field): findings.append({'kind':'field_mismatch','severity':'medium','product_id':ident,'field':field,'live':a.get(field),'fallback':b.get(field)})
        image=str(a.get('image') or '')
        if image and not (image.startswith('/assets/') or image.startswith('https://')): findings.append({'kind':'unexpected_image_reference','severity':'medium','product_id':ident,'field':'image','live':image,'fallback':b.get('image')})
    for key in ('currency','store_mode','version'):
        if live.get(key)!=fallback.get(key): findings.append({'kind':'catalog_header_mismatch','severity':'medium','product_id':None,'field':key,'live':live.get(key),'fallback':fallback.get(key)})
    state='attention' if any(x['severity']=='high' for x in findings) else 'warning' if findings else 'healthy'
    return {'contract':'wwcx.catalog-consistency.v1','generated_at':utcnow(),'state':state,'summary':{'live_products':len(li),'fallback_products':len(fi),'fallback_active':len(active),'fallback_inactive':len(inactive),'findings':len(findings),'high':sum(x['severity']=='high' for x in findings),'medium':sum(x['severity']=='medium' for x in findings)},'findings':findings[:500],'sources':{'live':LIVE,'fallback':FALLBACK},'catalog_mutation_performed':False,'checkout_mutation_performed':False}
def build(): return compare(fetch_json(LIVE),fetch_json(FALLBACK))
def markdown(d):
    s=d['summary']; lines=['# Catalog Consistency','',f"Generated: {d['generated_at']}",f"State: **{d['state']}**",f"Live products: **{s['live_products']}** · Active fallback products: **{s['fallback_active']}** · Inactive fallback records: **{s['fallback_inactive']}**",'', '## Findings','']
    lines += [f"- **{x['severity']} · {x['kind']}** — {x.get('product_id') or 'catalog'}" + (f" · {x.get('field')}" if x.get('field') else '') for x in d['findings']] or ['- None.']
    lines += ['','The bot is read-only. It never changes products, prices, Stripe links, checkout state, or storefront files.']; return '\n'.join(lines)+'\n'
def main():
    d=build(); STATUS.parent.mkdir(parents=True,exist_ok=True); STATUS.write_text(json.dumps(d,indent=2)+'\n'); STATUS.chmod(0o644); upsert_library_document(LIB,ROOT,'operations/catalog-consistency/current.md','Catalog Consistency',markdown(d)); print(json.dumps(d['summary'],sort_keys=True))
if __name__=='__main__':main()
