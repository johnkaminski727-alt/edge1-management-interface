"""Small standards-oriented IRC/IRCv3 server for the Edge1 Comms Relay."""

from __future__ import annotations

import base64
import socketserver
import ssl
import threading
from dataclasses import dataclass, field
from typing import Any

from .config import ListenerConfig, RelayConfig
from .storage import Account, CommsStore


SUPPORTED_CAPS = ("sasl", "message-tags", "server-time")


def parse_irc_line(line: str) -> tuple[dict[str, str], str | None, str, list[str]]:
    tags: dict[str, str] = {}
    prefix: str | None = None
    rest = line.strip("\r\n")
    if rest.startswith("@"):
        tag_text, _, rest = rest.partition(" ")
        for item in tag_text[1:].split(";"):
            key, sep, value = item.partition("=")
            tags[key] = value if sep else ""
    if rest.startswith(":"):
        prefix_text, _, rest = rest.partition(" ")
        prefix = prefix_text[1:]
    trailing: str | None = None
    if " :" in rest:
        middle, trailing = rest.split(" :", 1)
        pieces = middle.split()
    else:
        pieces = rest.split()
    if not pieces:
        return tags, prefix, "", []
    command = pieces[0].upper()
    params = pieces[1:]
    if trailing is not None:
        params.append(trailing)
    return tags, prefix, command, params


@dataclass
class IrcClientState:
    handler: Any
    nick: str | None = None
    username: str | None = None
    realname: str | None = None
    account: Account | None = None
    cap_negotiating: bool = False
    caps: set[str] = field(default_factory=set)
    sasl_waiting: bool = False
    registered: bool = False
    channels: set[str] = field(default_factory=set)

    @property
    def mask(self) -> str:
        nick = self.nick or "*"
        user = self.username or "unknown"
        return f"{nick}!{user}@edge1"


@dataclass
class IrcChannel:
    name: str
    topic: str = ""
    members: dict[int, IrcClientState] = field(default_factory=dict)


class IrcHub:
    def __init__(self, cfg: RelayConfig, store: CommsStore) -> None:
        self.cfg = cfg
        self.store = store
        self._lock = threading.RLock()
        self.clients: dict[int, IrcClientState] = {}
        self.channels: dict[str, IrcChannel] = {}

    def add_client(self, state: IrcClientState) -> None:
        with self._lock:
            self.clients[id(state)] = state

    def remove_client(self, state: IrcClientState, reason: str = "Client quit") -> None:
        with self._lock:
            for channel_name in list(state.channels):
                channel = self.channels.get(channel_name.lower())
                if channel:
                    self.broadcast(channel, f":{state.mask} QUIT :{reason}", exclude=state)
                    channel.members.pop(id(state), None)
                    if not channel.members:
                        self.channels.pop(channel_name.lower(), None)
            self.clients.pop(id(state), None)
        self.store.audit(state.account.username if state.account else None, "irc", "disconnect", state.nick, "ok", {})

    def find_nick(self, nick: str) -> IrcClientState | None:
        with self._lock:
            for client in self.clients.values():
                if client.nick and client.nick.lower() == nick.lower():
                    return client
        return None

    def get_channel(self, name: str) -> IrcChannel:
        key = name.lower()
        with self._lock:
            channel = self.channels.get(key)
            if channel is None:
                channel = IrcChannel(name=name)
                self.channels[key] = channel
            return channel

    def broadcast(self, channel: IrcChannel, line: str, *, exclude: IrcClientState | None = None) -> None:
        for member in list(channel.members.values()):
            if member is not exclude:
                member.handler.send_line(line)

    def summary(self) -> dict[str, Any]:
        with self._lock:
            channels = [
                {"name": channel.name, "members": len(channel.members), "topic": channel.topic}
                for channel in sorted(self.channels.values(), key=lambda item: item.name.lower())
            ]
            users = sum(1 for client in self.clients.values() if client.registered)
        return {"connected_users": users, "channels": channels}


class IrcRequestHandler(socketserver.StreamRequestHandler):
    server: "IrcServer"

    def setup(self) -> None:
        super().setup()
        self.state = IrcClientState(handler=self)
        self.server.hub.add_client(self.state)

    def finish(self) -> None:
        try:
            self.server.hub.remove_client(self.state)
        finally:
            super().finish()

    def send_line(self, line: str) -> None:
        payload = (line[: self.server.cfg.security.max_line_bytes - 2] + "\r\n").encode("utf-8", errors="replace")
        try:
            self.wfile.write(payload)
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    def numeric(self, code: int, text: str) -> None:
        target = self.state.nick or "*"
        self.send_line(f":{self.server.cfg.server_name} {code:03d} {target} {text}")

    def handle(self) -> None:
        while True:
            raw = self.rfile.readline(self.server.cfg.security.max_line_bytes + 1)
            if not raw:
                return
            if len(raw) > self.server.cfg.security.max_line_bytes:
                self.send_line(f":{self.server.cfg.server_name} ERROR :Line too long")
                return
            line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
            if not line:
                continue
            _, _, command, params = parse_irc_line(line)
            if not command:
                continue
            if command == "CAP":
                self.handle_cap(params)
            elif command == "AUTHENTICATE":
                self.handle_authenticate(params)
            elif command == "NICK":
                self.handle_nick(params)
            elif command == "USER":
                self.handle_user(params)
            elif command == "PING":
                token = params[-1] if params else self.server.cfg.server_name
                self.send_line(f":{self.server.cfg.server_name} PONG {self.server.cfg.server_name} :{token}")
            elif command == "PONG":
                pass
            elif command == "QUIT":
                return
            else:
                if not self.state.registered:
                    self.numeric(451, ":You have not registered")
                    continue
                self.handle_registered(command, params)

    def handle_cap(self, params: list[str]) -> None:
        if not params:
            return
        sub = params[0].upper()
        if sub == "LS":
            self.state.cap_negotiating = True
            self.send_line(f":{self.server.cfg.server_name} CAP * LS :{' '.join(SUPPORTED_CAPS)}")
        elif sub == "REQ" and len(params) >= 2:
            requested = {item for item in params[-1].split() if item}
            if requested.issubset(SUPPORTED_CAPS):
                self.state.caps.update(requested)
                self.send_line(f":{self.server.cfg.server_name} CAP * ACK :{' '.join(sorted(requested))}")
            else:
                self.send_line(f":{self.server.cfg.server_name} CAP * NAK :{' '.join(sorted(requested))}")
        elif sub == "END":
            self.state.cap_negotiating = False
            self.try_register()

    def handle_authenticate(self, params: list[str]) -> None:
        if not params:
            self.numeric(904, ":SASL authentication failed")
            return
        token = params[0]
        if token.upper() == "PLAIN":
            self.state.sasl_waiting = True
            self.send_line("AUTHENTICATE +")
            return
        if not self.state.sasl_waiting:
            self.numeric(904, ":SASL authentication failed")
            return
        self.state.sasl_waiting = False
        try:
            decoded = base64.b64decode(token, validate=True).decode("utf-8")
            parts = decoded.split("\x00")
            if len(parts) != 3:
                raise ValueError("invalid PLAIN payload")
            authcid, password = parts[1], parts[2]
        except (ValueError, UnicodeError):
            self.numeric(904, ":SASL authentication failed")
            return
        account = self.server.store.authenticate(authcid, password, protocol="irc")
        if account is None:
            self.numeric(904, ":SASL authentication failed")
            return
        self.state.account = account
        self.numeric(900, f"{self.state.nick or '*'}!{self.state.username or 'unknown'}@edge1 {account.username} :You are now logged in")
        self.numeric(903, ":SASL authentication successful")
        self.try_register()

    def handle_nick(self, params: list[str]) -> None:
        if not params:
            self.numeric(431, ":No nickname given")
            return
        nick = params[0][:32]
        if not nick or not (nick[0].isalpha() or nick[0] in "[]\\`_^{|}"):
            self.numeric(432, f"{nick} :Erroneous nickname")
            return
        existing = self.server.hub.find_nick(nick)
        if existing is not None and existing is not self.state:
            self.numeric(433, f"{nick} :Nickname is already in use")
            return
        old_mask = self.state.mask
        old_nick = self.state.nick
        self.state.nick = nick
        if old_nick and self.state.registered:
            for channel_name in self.state.channels:
                channel = self.server.hub.get_channel(channel_name)
                self.server.hub.broadcast(channel, f":{old_mask} NICK :{nick}")
        self.try_register()

    def handle_user(self, params: list[str]) -> None:
        if len(params) < 4:
            self.numeric(461, "USER :Not enough parameters")
            return
        if self.state.registered:
            self.numeric(462, ":You may not reregister")
            return
        self.state.username = params[0][:32]
        self.state.realname = params[3][:128]
        self.try_register()

    def try_register(self) -> None:
        if self.state.registered or self.state.cap_negotiating:
            return
        if not self.state.nick or not self.state.username:
            return
        if self.server.cfg.security.require_auth and self.state.account is None:
            return
        self.state.registered = True
        self.numeric(1, f":Welcome to {self.server.cfg.network_name} IRC, {self.state.mask}")
        self.numeric(2, f":Your host is {self.server.cfg.server_name}")
        self.numeric(5, "CHANTYPES=# PREFIX=(o)@ NETWORK=WW.CX CASEMAPPING=ascii :are supported by this server")
        actor = self.state.account.username if self.state.account else None
        self.server.store.audit(actor, "irc", "connect", self.state.nick, "ok", {})

    def handle_registered(self, command: str, params: list[str]) -> None:
        if command == "JOIN":
            self.handle_join(params)
        elif command == "PART":
            self.handle_part(params)
        elif command in {"PRIVMSG", "NOTICE"}:
            self.handle_message(command, params)
        elif command == "TOPIC":
            self.handle_topic(params)
        elif command == "NAMES":
            self.handle_names(params)
        elif command == "WHO":
            self.handle_who(params)
        else:
            self.numeric(421, f"{command} :Unknown command")

    def handle_join(self, params: list[str]) -> None:
        if not params:
            self.numeric(461, "JOIN :Not enough parameters")
            return
        for name in params[0].split(","):
            if not name.startswith("#") or len(name) > 64:
                self.numeric(403, f"{name} :No such channel")
                continue
            channel = self.server.hub.get_channel(name)
            channel.members[id(self.state)] = self.state
            self.state.channels.add(channel.name)
            self.server.hub.broadcast(channel, f":{self.state.mask} JOIN :{channel.name}")
            if channel.topic:
                self.numeric(332, f"{channel.name} :{channel.topic}")
            else:
                self.numeric(331, f"{channel.name} :No topic is set")
            self.send_names(channel)
            if self.server.cfg.retention.irc_history_enabled:
                actor = self.state.account.username if self.state.account else None
                self.server.store.record_irc(channel.name, actor, self.state.nick or "*", "join", None)

    def handle_part(self, params: list[str]) -> None:
        if not params:
            self.numeric(461, "PART :Not enough parameters")
            return
        name = params[0]
        channel = self.server.hub.channels.get(name.lower())
        if channel is None or id(self.state) not in channel.members:
            self.numeric(442, f"{name} :You're not on that channel")
            return
        reason = params[1] if len(params) > 1 else "Leaving"
        self.server.hub.broadcast(channel, f":{self.state.mask} PART {channel.name} :{reason}")
        channel.members.pop(id(self.state), None)
        self.state.channels.discard(channel.name)

    def handle_message(self, command: str, params: list[str]) -> None:
        if len(params) < 2:
            if command == "PRIVMSG":
                self.numeric(461, "PRIVMSG :Not enough parameters")
            return
        target, text = params[0], params[1]
        line = f":{self.state.mask} {command} {target} :{text}"
        if target.startswith("#"):
            channel = self.server.hub.channels.get(target.lower())
            if channel is None:
                self.numeric(403, f"{target} :No such channel")
                return
            if id(self.state) not in channel.members:
                self.numeric(404, f"{target} :Cannot send to channel")
                return
            self.server.hub.broadcast(channel, line, exclude=self.state)
            if command == "PRIVMSG" and self.server.cfg.retention.irc_history_enabled:
                actor = self.state.account.username if self.state.account else None
                self.server.store.record_irc(channel.name, actor, self.state.nick or "*", "privmsg", text)
        else:
            peer = self.server.hub.find_nick(target)
            if peer is None:
                self.numeric(401, f"{target} :No such nick")
                return
            peer.handler.send_line(line)
        actor = self.state.account.username if self.state.account else None
        self.server.store.audit(actor, "irc", command.lower(), target, "ok", {"bytes": len(text.encode("utf-8"))})

    def handle_topic(self, params: list[str]) -> None:
        if not params:
            self.numeric(461, "TOPIC :Not enough parameters")
            return
        channel = self.server.hub.channels.get(params[0].lower())
        if channel is None:
            self.numeric(403, f"{params[0]} :No such channel")
            return
        if len(params) == 1:
            self.numeric(332 if channel.topic else 331, f"{channel.name} :{channel.topic or 'No topic is set'}")
            return
        if id(self.state) not in channel.members:
            self.numeric(442, f"{channel.name} :You're not on that channel")
            return
        channel.topic = params[1][:390]
        self.server.hub.broadcast(channel, f":{self.state.mask} TOPIC {channel.name} :{channel.topic}")
        actor = self.state.account.username if self.state.account else None
        self.server.store.audit(actor, "irc", "topic", channel.name, "ok", {"bytes": len(channel.topic.encode("utf-8"))})

    def handle_names(self, params: list[str]) -> None:
        if not params:
            return
        channel = self.server.hub.channels.get(params[0].lower())
        if channel:
            self.send_names(channel)

    def send_names(self, channel: IrcChannel) -> None:
        names = " ".join(sorted(member.nick or "*" for member in channel.members.values()))
        self.numeric(353, f"= {channel.name} :{names}")
        self.numeric(366, f"{channel.name} :End of /NAMES list")

    def handle_who(self, params: list[str]) -> None:
        if not params:
            return
        channel = self.server.hub.channels.get(params[0].lower())
        if channel:
            for member in channel.members.values():
                self.numeric(352, f"{channel.name} {member.username or 'unknown'} edge1 {self.server.cfg.server_name} {member.nick or '*'} H :0 {member.realname or ''}")
        self.numeric(315, f"{params[0]} :End of /WHO list")


class IrcServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, address: tuple[str, int], cfg: RelayConfig, store: CommsStore, listener: ListenerConfig | None = None) -> None:
        self.cfg = cfg
        self.store = store
        self.hub = IrcHub(cfg, store)
        self.listener = listener or cfg.irc
        super().__init__(address, IrcRequestHandler, bind_and_activate=False)
        self.server_bind()
        self.server_activate()
        if self.listener.tls:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            context.load_cert_chain(self.listener.cert_file or "", self.listener.key_file or "")
            self.socket = context.wrap_socket(self.socket, server_side=True)
