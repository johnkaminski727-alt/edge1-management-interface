#!/usr/bin/env python3
from __future__ import annotations
import concurrent.futures,json,urllib.parse,urllib.robotparser
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.automation.automation_common import utcnow,upsert_library_document
from tools.automation.public_web_common import UA,fetch,public,decode,parse_html,sitemap_urls,load_sites
CFG=ROOT/'config/automation/public-websites.json';STATUS=Path('/var/www/edge1-status/seo-audit/status.json');LIB=Path('/var/lib/bigbird-ai-library/library.sqlite3')
def inspect(url,robots_text):
    rp=urllib.robotparser.RobotFileParser();rp.set_url(url);rp.parse(robots_text.splitlines())
    if not rp.can_fetch(UA,url):return {'url':url,'skipped':'robots_disallow','issues':[{'severity':'medium','code':'robots_disallow'}]}
    r=fetch(url,max_bytes=768*1024); row={'url':url,'fetch':public(r),'issues':[]}
    if not r['ok']:row['issues'].append({'severity':'high','code':'http_error','detail':str(r.get('status') or r.get('error'))});return row
    if r.get('content_type')!='text/html':return row
    m=parse_html(decode(r));row['meta']=m
    checks=[('title_missing',not m['title'],'medium'),('description_missing',not m['description'],'low'),('canonical_missing',not m['canonical'],'low'),('noindex','noindex' in m['robots'].lower(),'high'),('og_title_missing',not m['og_title'],'low'),('og_description_missing',not m['og_description'],'low')]
    for code,bad,sev in checks:
        if bad:row['issues'].append({'severity':sev,'code':code})
    if m['canonical']:
        try:
            a=urllib.parse.urlsplit(url);b=urllib.parse.urlsplit(urllib.parse.urljoin(url,m['canonical']))
            if (a.hostname or '').lower()!=(b.hostname or '').lower():row['issues'].append({'severity':'medium','code':'canonical_cross_host'})
        except Exception:row['issues'].append({'severity':'medium','code':'canonical_invalid'})
    return row
def build(max_per_site=100):
    site_rows=[]; all_issues=[]
    for site in load_sites(CFG):
        domain=site['domain'];base=site['base_url'];rob=fetch(base.rstrip('/')+'/robots.txt',max_bytes=512*1024);robots_text=decode(rob) if rob['ok'] else '';urls,maps=sitemap_urls(base.rstrip('/')+'/sitemap.xml',domain,max_urls=max_per_site)
        if not urls:urls=[base]
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex: pages=list(ex.map(lambda u:inspect(u,robots_text),urls))
        for page in pages:
            for issue in page.get('issues',[]):all_issues.append({'domain':domain,'url':page['url'],**issue})
        site_rows.append({'domain':domain,'sitemap_urls_discovered':len(urls),'sitemaps_checked':maps,'pages_checked':len(pages),'pages':pages})
    counts={s:sum(x['severity']==s for x in all_issues) for s in ('high','medium','low')};state='attention' if counts['high'] else 'warning' if counts['medium'] else 'healthy'
    return {'contract':'wwcx.seo-crawl-audit.v1','generated_at':utcnow(),'state':state,'summary':{'sites':len(site_rows),'pages_checked':sum(x['pages_checked'] for x in site_rows),'issues':len(all_issues),**counts},'sites':site_rows,'issues':all_issues[:1000],'mutation_performed':False,'crawl_bounded':True}
def md(d):
    s=d['summary'];lines=['# Public Website SEO/Crawl Audit','',f"Generated: {d['generated_at']}",f"State: **{d['state']}**",f"Pages checked: **{s['pages_checked']}** · Issues: **{s['issues']}** (high {s['high']}, medium {s['medium']}, low {s['low']})",'', '## Sites','']
    for x in d['sites']:lines.append(f"- **{x['domain']}** — {x['pages_checked']} pages checked from {len(x['sitemaps_checked'])} sitemap documents")
    lines += ['','## High/medium findings','']
    findings=[x for x in d['issues'] if x['severity'] in ('high','medium')]
    lines += [f"- **{x['severity']}** {x['domain']} — `{x['code']}` — {x['url']}" for x in findings[:100]] or ['- None.']
    lines += ['','This audit is read-only, bounded, and respects robots.txt.'];return '\n'.join(lines)+'\n'
def main():
    d=build();STATUS.parent.mkdir(parents=True,exist_ok=True);STATUS.write_text(json.dumps(d,indent=2)+'\n');STATUS.chmod(0o644);upsert_library_document(LIB,ROOT,'operations/seo-audit/current.md','Public Website SEO/Crawl Audit',md(d));print(json.dumps(d['summary'],sort_keys=True))
if __name__=='__main__':main()
