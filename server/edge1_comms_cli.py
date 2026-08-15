#!/usr/bin/env python3
"""Operator CLI for the WW.CX Edge1 Communications Relay."""
from __future__ import annotations
import argparse,difflib,getpass,json,sys
from pathlib import Path
from edge1_comms.config import ConfigError,config_from_dict,load_config,sanitized_config
from edge1_comms.config_control import apply_candidate,rollback_last,stage_config
from edge1_comms.storage import CommsStore
def make_parser():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config');sub=p.add_subparsers(dest='command',required=True);sub.add_parser('status');account=sub.add_parser('account');a=account.add_subparsers(dest='account_command',required=True);add=a.add_parser('add');add.add_argument('username');add.add_argument('--role',action='append',default=[]);add.add_argument('--password-stdin',action='store_true');a.add_parser('list')
    for n in ('enable','disable','password'):
        x=a.add_parser(n);x.add_argument('username');x.add_argument('--password-stdin',action='store_true') if n=='password' else None
    group=sub.add_parser('group');g=group.add_subparsers(dest='group_command',required=True);g.add_parser('list');ga=g.add_parser('add');ga.add_argument('name');ga.add_argument('description');ga.add_argument('--moderated',action='store_true');ga.add_argument('--retention-days',type=int)
    article=sub.add_parser('article');ar=article.add_subparsers(dest='article_command',required=True);al=ar.add_parser('list');al.add_argument('group');al.add_argument('--limit',type=int,default=100);archive=sub.add_parser('archive');av=archive.add_subparsers(dest='archive_command',required=True);ch=av.add_parser('channel');ch.add_argument('channel');ch.add_argument('group');ch.add_argument('subject');ch.add_argument('--author',required=True);ch.add_argument('--limit',type=int,default=100);audit=sub.add_parser('audit');audit.add_argument('--limit',type=int,default=100);maintenance=sub.add_parser('maintenance');m=maintenance.add_subparsers(dest='maintenance_command',required=True);m.add_parser('prune');config=sub.add_parser('config');c=config.add_subparsers(dest='config_command',required=True);v=c.add_parser('validate');v.add_argument('path');d=c.add_parser('diff');d.add_argument('old');d.add_argument('new');st=c.add_parser('stage');st.add_argument('path');st.add_argument('--state-dir',default='/var/lib/wwcx-comms/config-control');ap=c.add_parser('apply');ap.add_argument('--state-dir',default='/var/lib/wwcx-comms/config-control');ap.add_argument('--target',default='/etc/wwcx/comms-relay.json');rb=c.add_parser('rollback');rb.add_argument('--state-dir',default='/var/lib/wwcx-comms/config-control');rb.add_argument('--target',default='/etc/wwcx/comms-relay.json');return p
def output(v):print(json.dumps(v,indent=2,sort_keys=True))
def read_secret(stdin):
    value=sys.stdin.readline().rstrip('\r\n') if stdin else getpass.getpass('Password: ')
    if not stdin:
        confirm=getpass.getpass('Confirm password: ')
        if value!=confirm:raise SystemExit('passwords did not match')
    return value
def load_json(path):
    p=json.loads(Path(path).read_text());
    if not isinstance(p,dict):raise ConfigError('top-level configuration must be an object')
    config_from_dict(p);return p
def store_for(cfg):return CommsStore(cfg.database_path,password_iterations=cfg.security.password_iterations,min_password_length=cfg.security.min_password_length,default_news_days=cfg.retention.default_news_days,irc_history_days=cfg.retention.irc_history_days,audit_days=cfg.retention.audit_days)
def main():
    args=make_parser().parse_args()
    if args.command=='config':
        try:
            if args.config_command=='validate':output({'valid':True,'config':sanitized_config(config_from_dict(load_json(args.path)))});return 0
            if args.config_command=='stage':output(stage_config(args.path,args.state_dir));return 0
            if args.config_command=='apply':output(apply_candidate(args.state_dir,args.target));return 0
            if args.config_command=='rollback':output(rollback_last(args.state_dir,args.target));return 0
            old=json.dumps(load_json(args.old),indent=2,sort_keys=True).splitlines(True);new=json.dumps(load_json(args.new),indent=2,sort_keys=True).splitlines(True);sys.stdout.writelines(difflib.unified_diff(old,new,fromfile=args.old,tofile=args.new));return 0
        except (OSError,json.JSONDecodeError,ConfigError,ValueError) as e:print(f'configuration error: {e}',file=sys.stderr);return 2
    cfg=load_config(args.config);store=store_for(cfg)
    if args.command=='status':output({'config':sanitized_config(cfg),'storage':store.stats()});return 0
    if args.command=='maintenance':output({'removed':store.prune_retention()});store.checkpoint();return 0
    if args.command=='account':
        if args.account_command=='list':output(store.list_accounts());return 0
        if args.account_command=='add':
            try:store.add_account(args.username,read_secret(args.password_stdin),args.role)
            except ValueError as e:print(str(e),file=sys.stderr);return 2
            output({'created':args.username,'roles':sorted(set(args.role))});return 0
        if args.account_command=='password':
            try:ok=store.set_account_password(args.username,read_secret(args.password_stdin))
            except ValueError as e:print(str(e),file=sys.stderr);return 2
            if not ok:print('account not found',file=sys.stderr);return 3
            output({'password_updated':args.username});return 0
        enabled=args.account_command=='enable';ok=store.set_account_enabled(args.username,enabled)
        if not ok:print('account not found',file=sys.stderr);return 3
        output({'account':args.username,'enabled':enabled});return 0
    if args.command=='group':
        if args.group_command=='list':output(store.list_groups());return 0
        store.add_group(args.name,args.description,moderated=args.moderated,retention_days=args.retention_days);output({'created':args.name,'moderated':args.moderated});return 0
    if args.command=='article':output([{'id':r['id'],'message_id':r['message_id'],'subject':r['subject'],'author':r['author'],'date':r['date_rfc5322']} for r in store.articles_for_group(args.group,limit=args.limit)]);return 0
    if args.command=='archive':
        events=store.recent_irc(args.channel,args.limit);account=store.get_account(args.author)
        if not events or account is None or not account.enabled or not store.can_post(account,args.group):print('archive prerequisites not met',file=sys.stderr);return 4
        lines=[f"[{e['created_at_utc']}] <{e['nick']}> {e['body'] or ''}" if e['event']=='privmsg' else f"[{e['created_at_utc']}] * {e['nick']} {e['event']}" for e in events];article=store.post_article(group_name=args.group,author=f'{args.author} <{args.author}@users.ww.cx>',account=args.author,subject=args.subject,body='\n'.join(lines),extra_headers={'X-WWCX-Archive-Source':f'irc:{args.channel}'},server_name=cfg.server_name);output({'message_id':article['message_id'],'article_id':article['id'],'events':len(events)});return 0
    if args.command=='audit':output(store.recent_audit(args.limit));return 0
    return 1
if __name__=='__main__':raise SystemExit(main())
