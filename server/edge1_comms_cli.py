#!/usr/bin/env python3
"""Operator CLI for the WW.CX Edge1 Communications Relay."""

from __future__ import annotations

import argparse
import difflib
import getpass
import json
import sys
from pathlib import Path

from edge1_comms.config import ConfigError, config_from_dict, load_config, sanitized_config
from edge1_comms.config_control import apply_candidate, rollback_last, stage_config
from edge1_comms.ingest import IngestError, run_ingestion
from edge1_comms.storage import CommsStore


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('status')

    account = sub.add_parser('account')
    accounts = account.add_subparsers(dest='account_command', required=True)
    add = accounts.add_parser('add')
    add.add_argument('username')
    add.add_argument('--role', action='append', default=[])
    add.add_argument('--password-stdin', action='store_true')
    accounts.add_parser('list')
    for name in ('enable', 'disable', 'password'):
        item = accounts.add_parser(name)
        item.add_argument('username')
        if name == 'password':
            item.add_argument('--password-stdin', action='store_true')

    group = sub.add_parser('group')
    groups = group.add_subparsers(dest='group_command', required=True)
    groups.add_parser('list')
    group_add = groups.add_parser('add')
    group_add.add_argument('name')
    group_add.add_argument('description')
    group_add.add_argument('--moderated', action='store_true')
    group_add.add_argument('--retention-days', type=int)

    article = sub.add_parser('article')
    articles = article.add_subparsers(dest='article_command', required=True)
    article_list = articles.add_parser('list')
    article_list.add_argument('group')
    article_list.add_argument('--limit', type=int, default=100)

    archive = sub.add_parser('archive')
    archives = archive.add_subparsers(dest='archive_command', required=True)
    channel = archives.add_parser('channel')
    channel.add_argument('channel')
    channel.add_argument('group')
    channel.add_argument('subject')
    channel.add_argument('--author', required=True)
    channel.add_argument('--limit', type=int, default=100)

    ingest = sub.add_parser('ingest')
    ingests = ingest.add_subparsers(dest='ingest_command', required=True)
    ingests.add_parser('status')
    ingest_run = ingests.add_parser('run')
    ingest_run.add_argument('--dry-run', action='store_true')

    audit = sub.add_parser('audit')
    audit.add_argument('--limit', type=int, default=100)

    maintenance = sub.add_parser('maintenance')
    maintenance_sub = maintenance.add_subparsers(dest='maintenance_command', required=True)
    maintenance_sub.add_parser('prune')

    config = sub.add_parser('config')
    configs = config.add_subparsers(dest='config_command', required=True)
    validate = configs.add_parser('validate')
    validate.add_argument('path')
    diff = configs.add_parser('diff')
    diff.add_argument('old')
    diff.add_argument('new')
    stage = configs.add_parser('stage')
    stage.add_argument('path')
    stage.add_argument('--state-dir', default='/var/lib/wwcx-comms/config-control')
    apply = configs.add_parser('apply')
    apply.add_argument('--state-dir', default='/var/lib/wwcx-comms/config-control')
    apply.add_argument('--target', default='/etc/wwcx/comms-relay.json')
    rollback = configs.add_parser('rollback')
    rollback.add_argument('--state-dir', default='/var/lib/wwcx-comms/config-control')
    rollback.add_argument('--target', default='/etc/wwcx/comms-relay.json')
    return parser


def output(value: object) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def read_secret(stdin: bool) -> str:
    value = sys.stdin.readline().rstrip('\r\n') if stdin else getpass.getpass('Password: ')
    if not stdin:
        confirm = getpass.getpass('Confirm password: ')
        if value != confirm:
            raise SystemExit('passwords did not match')
    return value


def load_json(path: str) -> dict[str, object]:
    payload = json.loads(Path(path).read_text())
    if not isinstance(payload, dict):
        raise ConfigError('top-level configuration must be an object')
    config_from_dict(payload)
    return payload


def store_for(cfg: object) -> CommsStore:
    return CommsStore(
        cfg.database_path,
        password_iterations=cfg.security.password_iterations,
        min_password_length=cfg.security.min_password_length,
        default_news_days=cfg.retention.default_news_days,
        irc_history_days=cfg.retention.irc_history_days,
        audit_days=cfg.retention.audit_days,
    )


def main() -> int:
    args = make_parser().parse_args()
    if args.command == 'config':
        try:
            if args.config_command == 'validate':
                output({'valid': True, 'config': sanitized_config(config_from_dict(load_json(args.path)))})
                return 0
            if args.config_command == 'stage':
                output(stage_config(args.path, args.state_dir))
                return 0
            if args.config_command == 'apply':
                output(apply_candidate(args.state_dir, args.target))
                return 0
            if args.config_command == 'rollback':
                output(rollback_last(args.state_dir, args.target))
                return 0
            old = json.dumps(load_json(args.old), indent=2, sort_keys=True).splitlines(True)
            new = json.dumps(load_json(args.new), indent=2, sort_keys=True).splitlines(True)
            sys.stdout.writelines(difflib.unified_diff(old, new, fromfile=args.old, tofile=args.new))
            return 0
        except (OSError, json.JSONDecodeError, ConfigError, ValueError) as exc:
            print(f'configuration error: {exc}', file=sys.stderr)
            return 2

    cfg = load_config(args.config)
    store = store_for(cfg)
    if args.command == 'status':
        output({'config': sanitized_config(cfg), 'storage': store.stats()})
        return 0
    if args.command == 'maintenance':
        output({'removed': store.prune_retention()})
        store.checkpoint()
        return 0
    if args.command == 'ingest':
        if args.ingest_command == 'status':
            output({'config': sanitized_config(cfg)['ingestion'], 'state': store.list_ingest_state(), 'items': store.ingest_count()})
            return 0
        try:
            output(run_ingestion(cfg, store, dry_run=args.dry_run))
            return 0
        except (IngestError, OSError, ValueError) as exc:
            print(f'ingestion error: {exc}', file=sys.stderr)
            return 5
    if args.command == 'account':
        if args.account_command == 'list':
            output(store.list_accounts())
            return 0
        if args.account_command == 'add':
            try:
                store.add_account(args.username, read_secret(args.password_stdin), args.role)
            except ValueError as exc:
                print(str(exc), file=sys.stderr)
                return 2
            output({'created': args.username, 'roles': sorted(set(args.role))})
            return 0
        if args.account_command == 'password':
            try:
                ok = store.set_account_password(args.username, read_secret(args.password_stdin))
            except ValueError as exc:
                print(str(exc), file=sys.stderr)
                return 2
            if not ok:
                print('account not found', file=sys.stderr)
                return 3
            output({'password_updated': args.username})
            return 0
        enabled = args.account_command == 'enable'
        ok = store.set_account_enabled(args.username, enabled)
        if not ok:
            print('account not found', file=sys.stderr)
            return 3
        output({'account': args.username, 'enabled': enabled})
        return 0
    if args.command == 'group':
        if args.group_command == 'list':
            output(store.list_groups())
            return 0
        store.add_group(args.name, args.description, moderated=args.moderated, retention_days=args.retention_days)
        output({'created': args.name, 'moderated': args.moderated})
        return 0
    if args.command == 'article':
        output([
            {'id': row['id'], 'message_id': row['message_id'], 'subject': row['subject'], 'author': row['author'], 'date': row['date_rfc5322']}
            for row in store.articles_for_group(args.group, limit=args.limit)
        ])
        return 0
    if args.command == 'archive':
        events = store.recent_irc(args.channel, args.limit)
        account = store.get_account(args.author)
        if not events or account is None or not account.enabled or not store.can_post(account, args.group):
            print('archive prerequisites not met', file=sys.stderr)
            return 4
        lines = [
            f"[{event['created_at_utc']}] <{event['nick']}> {event['body'] or ''}"
            if event['event'] == 'privmsg'
            else f"[{event['created_at_utc']}] * {event['nick']} {event['event']}"
            for event in events
        ]
        article = store.post_article(
            group_name=args.group,
            author=f'{args.author} <{args.author}@users.ww.cx>',
            account=args.author,
            subject=args.subject,
            body='\n'.join(lines),
            extra_headers={'X-WWCX-Archive-Source': f'irc:{args.channel}'},
            server_name=cfg.server_name,
        )
        output({'message_id': article['message_id'], 'article_id': article['id'], 'events': len(events)})
        return 0
    if args.command == 'audit':
        output(store.recent_audit(args.limit))
        return 0
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
