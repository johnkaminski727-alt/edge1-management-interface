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
from edge1_comms.storage import CommsStore


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", help="Path to comms-relay JSON configuration")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="Show sanitized configuration and storage counts")
    account = sub.add_parser("account", help="Manage local communications accounts")
    account_sub = account.add_subparsers(dest="account_command", required=True)
    add = account_sub.add_parser("add")
    add.add_argument("username")
    add.add_argument("--role", action="append", default=[])
    add.add_argument("--password-stdin", action="store_true")
    account_sub.add_parser("list")
    for name in ("enable", "disable", "password"):
        item = account_sub.add_parser(name)
        item.add_argument("username")
        if name == "password":
            item.add_argument("--password-stdin", action="store_true")
    group = sub.add_parser("group", help="Manage NNTP newsgroups")
    group_sub = group.add_subparsers(dest="group_command", required=True)
    group_sub.add_parser("list")
    group_add = group_sub.add_parser("add")
    group_add.add_argument("name")
    group_add.add_argument("description")
    group_add.add_argument("--moderated", action="store_true")
    group_add.add_argument("--retention-days", type=int, default=3650)
    article = sub.add_parser("article", help="Inspect NNTP articles")
    article_sub = article.add_subparsers(dest="article_command", required=True)
    article_list = article_sub.add_parser("list")
    article_list.add_argument("group")
    article_list.add_argument("--limit", type=int, default=100)
    archive = sub.add_parser("archive", help="Create a news article from retained IRC channel history")
    archive_sub = archive.add_subparsers(dest="archive_command", required=True)
    channel = archive_sub.add_parser("channel")
    channel.add_argument("channel")
    channel.add_argument("group")
    channel.add_argument("subject")
    channel.add_argument("--author", required=True)
    channel.add_argument("--limit", type=int, default=100)
    audit = sub.add_parser("audit", help="Show recent sanitized audit metadata")
    audit.add_argument("--limit", type=int, default=100)
    config = sub.add_parser("config", help="Validate or diff configuration")
    config_sub = config.add_subparsers(dest="config_command", required=True)
    validate = config_sub.add_parser("validate")
    validate.add_argument("path")
    diff = config_sub.add_parser("diff")
    diff.add_argument("old")
    diff.add_argument("new")
    stage = config_sub.add_parser("stage")
    stage.add_argument("path")
    stage.add_argument("--state-dir", default="/var/lib/wwcx-comms/config-control")
    apply_item = config_sub.add_parser("apply")
    apply_item.add_argument("--state-dir", default="/var/lib/wwcx-comms/config-control")
    apply_item.add_argument("--target", default="/etc/wwcx/comms-relay.json")
    rollback = config_sub.add_parser("rollback")
    rollback.add_argument("--state-dir", default="/var/lib/wwcx-comms/config-control")
    rollback.add_argument("--target", default="/etc/wwcx/comms-relay.json")
    return parser


def read_secret(from_stdin: bool) -> str:
    if from_stdin:
        value = sys.stdin.readline().rstrip("\r\n")
    else:
        value = getpass.getpass("Password: ")
        confirm = getpass.getpass("Confirm password: ")
        if value != confirm:
            raise SystemExit("passwords did not match")
    if not value:
        raise SystemExit("password must not be empty")
    return value


def load_json_config(path: str) -> dict[str, object]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ConfigError("top-level configuration must be an object")
    config_from_dict(payload)
    return payload


def output(value: object) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def main() -> int:
    args = make_parser().parse_args()
    if args.command == "config":
        try:
            if args.config_command == "validate":
                payload = load_json_config(args.path)
                output({"valid": True, "config": sanitized_config(config_from_dict(payload))})
                return 0
            if args.config_command == "stage":
                output(stage_config(args.path, args.state_dir))
                return 0
            if args.config_command == "apply":
                output(apply_candidate(args.state_dir, args.target))
                return 0
            if args.config_command == "rollback":
                output(rollback_last(args.state_dir, args.target))
                return 0
            old = json.dumps(load_json_config(args.old), indent=2, sort_keys=True).splitlines(True)
            new = json.dumps(load_json_config(args.new), indent=2, sort_keys=True).splitlines(True)
            sys.stdout.writelines(difflib.unified_diff(old, new, fromfile=args.old, tofile=args.new))
            return 0
        except (OSError, json.JSONDecodeError, ConfigError) as exc:
            print(f"configuration error: {exc}", file=sys.stderr)
            return 2
    cfg = load_config(args.config)
    store = CommsStore(cfg.database_path, password_iterations=cfg.security.password_iterations)
    if args.command == "status":
        output({"config": sanitized_config(cfg), "storage": store.stats()})
        return 0
    if args.command == "account":
        if args.account_command == "list":
            output(store.list_accounts())
            return 0
        if args.account_command == "add":
            password = read_secret(args.password_stdin)
            store.add_account(args.username, password, args.role)
            output({"created": args.username, "roles": sorted(set(args.role))})
            return 0
        if args.account_command == "password":
            password = read_secret(args.password_stdin)
            if not store.set_account_password(args.username, password):
                print("account not found", file=sys.stderr)
                return 3
            output({"password_updated": args.username})
            return 0
        enabled = args.account_command == "enable"
        if not store.set_account_enabled(args.username, enabled):
            print("account not found", file=sys.stderr)
            return 3
        output({"account": args.username, "enabled": enabled})
        return 0
    if args.command == "group":
        if args.group_command == "list":
            output(store.list_groups())
            return 0
        store.add_group(args.name, args.description, moderated=args.moderated, retention_days=args.retention_days)
        output({"created": args.name, "moderated": args.moderated, "retention_days": args.retention_days})
        return 0
    if args.command == "article":
        rows = store.articles_for_group(args.group, limit=args.limit)
        output([{"id": row["id"], "message_id": row["message_id"], "subject": row["subject"], "author": row["author"], "date": row["date_rfc5322"]} for row in rows])
        return 0
    if args.command == "archive":
        events = store.recent_irc(args.channel, args.limit)
        if not events:
            print("no retained IRC history for channel", file=sys.stderr)
            return 4
        account = store.get_account(args.author)
        if account is None or not account.enabled:
            print("author account not found or disabled", file=sys.stderr)
            return 4
        if not store.can_post(account, args.group):
            print("author account cannot post to target group", file=sys.stderr)
            return 4
        lines = []
        for event in events:
            stamp = event["created_at_utc"]
            nick = event["nick"]
            if event["event"] == "privmsg":
                lines.append(f"[{stamp}] <{nick}> {event['body'] or ''}")
            else:
                lines.append(f"[{stamp}] * {nick} {event['event']}")
        article = store.post_article(group_name=args.group, author=f"{args.author} <{args.author}@users.ww.cx>", account=args.author, subject=args.subject, body="\n".join(lines), extra_headers={"X-WWCX-Archive-Source": f"irc:{args.channel}"}, server_name=cfg.server_name)
        output({"message_id": article["message_id"], "article_id": article["id"], "events": len(events)})
        return 0
    if args.command == "audit":
        output(store.recent_audit(args.limit))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
