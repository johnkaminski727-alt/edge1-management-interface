#!/usr/bin/env python3
"""Canonical Edge1 application registry and authorization-aware navigation view."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "src" / "web" / "shared" / "intelligence-nav.json"
CONTRACT = "wwcx.edge1-application-registry.v1"

def load_registry(path: Path = DEFAULT_REGISTRY) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("contract") != CONTRACT or data.get("navigation_grants_authorization") is not False:
        raise ValueError("application registry safety contract mismatch")
    modules = data.get("modules")
    if not isinstance(modules, list) or not modules:
        raise ValueError("application registry is empty")
    seen=set()
    for module in modules:
        if set(module) != {"id","label","href","section","sort_order","required_scopes","enabled"}:
            raise ValueError("application registry module fields mismatch")
        if module["id"] in seen:
            raise ValueError("duplicate application id")
        seen.add(module["id"])
        if not isinstance(module["required_scopes"], list) or not module["required_scopes"]:
            raise ValueError("application must declare required scopes")
        if not str(module["href"]).startswith("/"):
            raise ValueError("application route must be absolute")
    return data

def authorized_modules(scopes: Iterable[str], path: Path = DEFAULT_REGISTRY) -> list[dict]:
    """Return menu entries visible to an already-authenticated scope set.

    This is presentation filtering only. Route/API authorization remains mandatory.
    """
    granted=set(scopes)
    modules=load_registry(path)["modules"]
    visible=[]
    for module in modules:
        if module["enabled"] is not True:
            continue
        required=set(module["required_scopes"])
        if required.issubset(granted):
            visible.append(dict(module))
    return sorted(visible, key=lambda item:(item["sort_order"], item["id"]))
