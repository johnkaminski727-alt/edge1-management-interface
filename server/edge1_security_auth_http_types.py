"""Request and response value objects for the Edge1 Security HTTP boundary."""
from __future__ import annotations

import dataclasses
import re
from typing import Mapping

LOOPBACKS = {"127.0.0.1", "::1"}
COOKIE_VALUE_RE = re.compile(r"^[A-Za-z0-9_-]{32,256}$")


@dataclasses.dataclass(frozen=True)
class HttpRequest:
    method: str
    path: str
    headers: Mapping[str, str]
    body: bytes = b""
    remote_addr: str = "127.0.0.1"
    scheme: str = "https"
    host: str = "edge1.ww.cx"


@dataclasses.dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: tuple[tuple[str, str], ...]
    body: bytes
