from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class MessagingGatewayError(RuntimeError):
    """Raised when the internal messaging management API cannot be used safely."""


@dat