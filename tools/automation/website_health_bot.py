#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT))
from tools.automation.automation_common import utcnow, upsert_library_document
from tools.automation.public_web_common import fetch,public,decode,parse_html,load_sites
CFG=ROOT/'config/automation/public-websites.json'; STATUS=Path('/var/www/edge1-status/website-health/status.json'); LIB=Path('/var/lib/bigbird-ai-library/library.sqlite3')
def build():
    sites=[]; issues=[]
    for item in load_sites(CFG):
        domain=item['domain']; base=item['base_url']; root=fetch(base); robots=fetch(base.rstrip('/')+'/robots.txt',max_bytes=512*1024); sitemap=fetch(base.rstrip('/')+'/sitemap.xml',max_bytes=1024*1024); meta=parse_html(decode(root)) if root['ok'] and root.get('content_type')=='text/html' else {}
        row={'domain':domain,'root':public(root),'robots':public(robots),'sitemap':public(sitemap),'root_meta':meta}; sites.append(row)
        for key,r in [('root',root),('robots',robots),('sitemap',sitemap)]:
            if not r['ok']:issues.append({'domain':domain,'check':key,'severity':'high' if key=='root' else 'medium','detail':f"HTTP {r.get('status') or r.get('error','unavailable')}"})
        if root['ok'] and root.get('content_type')=='text/html':
            if not meta.get('title'):issues.append({'domain':domain,'check':'title','severity':'medium','detail':'Homepage title missing'})
            if 'noindex' in (meta.get('robots') or '').lower():issues.append({'domain':domain,'check':'robots_meta','severity':'high','detail':'Homepage has noindex'})
    return {'contract':'wwcx.website-health.v1','generated_at':utcnow(),'state':'attention' if any(x['severity']=='high' for x in issues) else 'warning' if issues else 'healthy','sites':sites,'issues':issues,'mutation_performed':False}
def md(d):
    lines=['# Public Website Health','',f"Generated: {d['generated_at']}",f"State: **{d['state']}**",'', '## Sites','']
    for x in d['sites']:lines.append(f"- **{x['domain']}** — root {x['root'].get('status')} · robots {x['robots'].get('status')} · sitemap {x['sitemap'].get('status')}")
    lines += ['','## Issues','']+([f"- **{x['severity']}** {x['domain']} / {x['check']}: {x['detail']}" for x in d['issues']] or ['- None.'])+['','Read-only external checks; no site content is modified.'];return '\n'.join(lines)+'\n'
def main():
    d=build(); STATUS.parent.mkdir(parents=True,exist_ok=True);STATUS.write_text(json.dumps(d,indent=2)+'\n');STATUS.chmod(0o644);upsert_library_document(LIB,ROOT,'operations/website-health/current.md','Public Website Health',md(d));print(json.dumps({'state':d['state'],'sites':len(d['sites']),'issues':len(d['issues'])},sort_keys=True))
if __name__=='__main__':main()
