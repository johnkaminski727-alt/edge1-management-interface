#!/usr/bin/env python3
"""Validate the WW.CX Edge1 Communications Relay foundation and protocol paths."""

from __future__ import annotations

import json
import secrets
import socket
import sys
import tempfile
import threading
import urllib.request
from dataclasses import replace
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVER_ROOT = REPO_ROOT / "server"
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from edge1_comms.config import ConfigError, ListenerConfig, RelayConfig, config_from_dict
from edge1_comms.control import ControlServer
from edge1_comms.config_control import apply_candidate, rollback_last, stage_config
from edge1_comms.irc import IrcServer, parse_irc_line
from edge1_comms.nntp import NntpServer, parse_range
from edge1_comms.storage import CommsStore


TEST_SECRET = secrets.token_urlsafe(24)


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def recv_until(sock: socket.socket, marker: bytes, *, limit: int = 100) -> bytes:
    data = bytearray()
    for _ in range(limit):
        chunk = sock.recv(4096)
        if not chunk:
            break
        data.extend(chunk)
        if marker in data:
            break
    return bytes(data)


def send_line(sock: socket.socket, line: str) -> None:
    sock.sendall((line + "\r\n").encode("utf-8"))


def start_server(server: object) -> threading.Thread:
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    thread.start()
    return thread


def stop_server(server: object, thread: threading.Thread) -> None:
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)
    check(not thread.is_alive(), "server thread did not stop")


def validate_config() -> None:
    example = json.loads((REPO_ROOT / "config" / "comms-relay.example.json").read_text(encoding="utf-8"))
    cfg = config_from_dict(example)
    check(cfg.irc.host == "127.0.0.1", "example IRC bind must be loopback")
    unsafe = json.loads(json.dumps(example))
    unsafe["network_exposure"]["enabled"] = True
    unsafe["listeners"]["irc"]["host"] = "0.0.0.0"
    unsafe["listeners"]["irc"]["tls"] = False
    try:
        config_from_dict(unsafe)
    except ConfigError:
        pass
    else:
        raise AssertionError("plaintext public IRC bind was accepted")


def validate_config_control(tmp: Path) -> None:
    example = REPO_ROOT / "config" / "comms-relay.example.json"
    state = tmp / "config-control"
    target = tmp / "running.json"
    original = json.loads(example.read_text(encoding="utf-8"))
    original["network_name"] = "WW.CX-OLD"
    target.write_text(json.dumps(original), encoding="utf-8")
    staged = stage_config(example, state)
    check(len(staged["sha256"]) == 64, "candidate hash missing")
    applied = apply_candidate(state, target)
    check(applied["backup"] is not None and applied["restart_required"], "apply did not create rollback evidence")
    check(json.loads(target.read_text(encoding="utf-8"))["network_name"] == "WW.CX", "candidate not applied")
    rolled = rollback_last(state, target)
    check(rolled["restart_required"], "rollback restart marker missing")
    check(json.loads(target.read_text(encoding="utf-8"))["network_name"] == "WW.CX-OLD", "rollback did not restore prior config")


def validate_parsers() -> None:
    tags, prefix, command, params = parse_irc_line("@time=123 :nick!u@h PRIVMSG #edge1 :hello world")
    check(tags["time"] == "123" and prefix == "nick!u@h" and command == "PRIVMSG", "IRC parser failed")
    check(params == ["#edge1", "hello world"], "IRC trailing parameter parse failed")
    check(parse_range("4-9") == (4, 9), "NNTP range parse failed")


def validate_storage(tmp: Path) -> CommsStore:
    store = CommsStore(tmp / "comms.sqlite3", password_iterations=100_000)
    store.add_account("john", TEST_SECRET, ["founder"])
    check(store.authenticate("john", TEST_SECRET, protocol="test") is not None, "valid password rejected")
    check(store.authenticate("john", TEST_SECRET + "-wrong", protocol="test") is None, "invalid password accepted")
    account = store.get_account("john")
    check(account is not None and store.can_post(account, "wwcx.announce"), "founder cannot post moderated group")
    article = store.post_article(
        group_name="wwcx.test",
        author="John <john@users.ww.cx>",
        account="john",
        subject="Storage validation",
        body="hello from storage",
        server_name="edge1.ww.cx",
    )
    check(article["message_id"].startswith("<"), "message id not generated")
    check(store.stats()["articles"] == 1, "article count incorrect")
    return store


def test_irc(cfg: RelayConfig, store: CommsStore) -> None:
    server = IrcServer(("127.0.0.1", 0), cfg, store, listener=ListenerConfig("127.0.0.1", 16667))
    thread = start_server(server)
    try:
        sock = socket.create_connection(server.server_address, timeout=2)
        sock.settimeout(2)
        send_line(sock, "CAP LS 302")
        data = recv_until(sock, b" CAP * LS ")
        check(b"sasl" in data, "IRC CAP LS did not advertise SASL")
        send_line(sock, "NICK relaytest")
        send_line(sock, "USER relaytest 0 * :Relay Test")
        send_line(sock, "CAP END")
        check(b" 001 relaytest " in recv_until(sock, b" 001 relaytest "), "IRC registration failed")
        send_line(sock, "JOIN #edge1")
        join_data = recv_until(sock, b" 366 relaytest #edge1 ")
        check(b"JOIN :#edge1" in join_data, "IRC JOIN failed")
        send_line(sock, "TOPIC #edge1 :Edge1 relay validation")
        check(b"TOPIC #edge1 :Edge1 relay validation" in recv_until(sock, b"Edge1 relay validation"), "IRC TOPIC failed")
        send_line(sock, "QUIT :test complete")
        sock.close()
    finally:
        stop_server(server, thread)


def read_nntp_response(sock: socket.socket, *, multiline: bool = False) -> bytes:
    first = recv_until(sock, b"\n")
    if not multiline:
        return first
    data = bytearray(first)
    while b"\r\n.\r\n" not in data and b"\n.\n" not in data:
        data.extend(sock.recv(4096))
    return bytes(data)


def test_nntp(cfg: RelayConfig, store: CommsStore) -> None:
    server = NntpServer(("127.0.0.1", 0), cfg, store, listener=ListenerConfig("127.0.0.1", 1119))
    thread = start_server(server)
    try:
        sock = socket.create_connection(server.server_address, timeout=2)
        sock.settimeout(2)
        check(read_nntp_response(sock).startswith(b"200 "), "NNTP greeting missing")
        send_line(sock, "GROUP wwcx.test")
        check(read_nntp_response(sock).startswith(b"211 "), "NNTP GROUP failed")
        send_line(sock, "POST")
        check(read_nntp_response(sock).startswith(b"340 "), "NNTP POST not accepted")
        article = (
            "From: Relay Test <relaytest@users.ww.cx>\r\n"
            "Subject: NNTP integration validation\r\n"
            "Newsgroups: wwcx.test\r\n"
            "\r\n"
            "hello via NNTP\r\n"
            ".\r\n"
        )
        sock.sendall(article.encode("utf-8"))
        post_response = read_nntp_response(sock)
        check(post_response.startswith(b"240 "), f"NNTP post failed: {post_response!r}")
        send_line(sock, "OVER 1-")
        overview = read_nntp_response(sock, multiline=True)
        check(b"NNTP integration validation" in overview, "NNTP OVER omitted posted article")
        send_line(sock, "QUIT")
        sock.close()
    finally:
        stop_server(server, thread)


def test_control(cfg: RelayConfig, store: CommsStore, tmp: Path) -> None:
    web = tmp / "web"
    web.mkdir()
    (web / "index.html").write_text("ok", encoding="utf-8")
    server = ControlServer(("127.0.0.1", 0), cfg, store, web_root=web, irc_summary=lambda: {"connected_users": 0, "channels": []})
    thread = start_server(server)
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}/api/comms/status"
        with urllib.request.urlopen(url, timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))
        check(payload["service"] == "edge1-comms-relay", "control status service mismatch")
        check(payload["federation"] == {"irc": "disabled", "nntp": "disabled"}, "federation safety status incorrect")
    finally:
        stop_server(server, thread)


def main() -> int:
    validate_config()
    validate_parsers()
    with tempfile.TemporaryDirectory(prefix="edge1-comms-") as name:
        tmp = Path(name)
        validate_config_control(tmp)
        store = validate_storage(tmp)
        cfg = replace(
            RelayConfig(),
            database_path=str(tmp / "comms.sqlite3"),
            security=replace(
                RelayConfig().security,
                password_iterations=100_000,
                require_auth=False,
                allow_anonymous_irc=True,
                allow_anonymous_nntp_read=True,
                allow_anonymous_nntp_post=True,
            ),
        )
        cfg.validate()
        test_irc(cfg, store)
        test_nntp(cfg, store)
        test_control(cfg, store, tmp)
    print("PASS validate_comms_relay")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
