#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
import mail_openpgp_policy
CONTRACT = "wwcx.openpgp-outbound-senders.v1"
DEFAULT_POLICY = Path("/etc/wwcx/outbound-mail/openpgp-policy.json")
DEFAULT_SENDERS = Path("/etc/wwcx/outbound-mail/openpgp-senders.json")
class OpenPGPOutboundRuntimeError(RuntimeError): pass

def _load(path: Path) -> dict[str, Any]:
    try: data=json.loads(path.read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError) as exc: raise OpenPGPOutboundRuntimeError("OpenPGP runtime configuration unavailable") from exc
    if not isinstance(data,dict): raise OpenPGPOutboundRuntimeError("OpenPGP runtime configuration is invalid")
    return data

def validate_senders(data: dict[str, Any]) -> dict[str, Any]:
    if data.get("contract") != CONTRACT: raise OpenPGPOutboundRuntimeError("unsupported OpenPGP sender contract")
    if data.get("enabled") is not True or data.get("deployment_authorized") is not True: raise OpenPGPOutboundRuntimeError("OpenPGP sender runtime is not authorized")
    senders=data.get("senders")
    if not isinstance(senders,dict) or not senders: raise OpenPGPOutboundRuntimeError("OpenPGP sender map is empty")
    for address,item in senders.items():
        if not isinstance(address,str) or "@" not in address or address != address.casefold(): raise OpenPGPOutboundRuntimeError("OpenPGP sender address is invalid")
        if not isinstance(item,dict) or item.get("mode") not in mail_openpgp_policy.MODES: raise OpenPGPOutboundRuntimeError("OpenPGP sender mode is invalid")
        fp="".join(str(item.get("signing_fingerprint","")).split()).upper()
        if len(fp) not in {40,64} or any(c not in "0123456789ABCDEF" for c in fp): raise OpenPGPOutboundRuntimeError("OpenPGP sender fingerprint is invalid")
    return data

class RuntimeOpenPGPResolver:
    def __init__(self,policy_path: str|Path=DEFAULT_POLICY,senders_path: str|Path=DEFAULT_SENDERS):
        self.policy_path=Path(policy_path); self.senders_path=Path(senders_path)
    def __call__(self,request: dict[str,Any]) -> dict[str,Any]|None:
        if not isinstance(request,dict): raise OpenPGPOutboundRuntimeError("outbound request is invalid")
        sender=str(request.get("from_address","")).strip().casefold(); recipients=request.get("recipients")
        if not sender or not isinstance(recipients,list) or not recipients: raise OpenPGPOutboundRuntimeError("outbound OpenPGP request is incomplete")
        senders=validate_senders(_load(self.senders_path)); rule=senders["senders"].get(sender)
        if rule is None: return None
        policy=mail_openpgp_policy.validate_policy(_load(self.policy_path))
        if policy.get("enabled") is not True or policy.get("deployment_authorized") is not True: raise OpenPGPOutboundRuntimeError("OpenPGP mail policy is not authorized")
        resolved=mail_openpgp_policy.resolve_mode(policy,str(rule["mode"]),[],len(recipients))
        if resolved["encrypt"]: raise OpenPGPOutboundRuntimeError("recipient encryption is not commissioned in this resolver")
        if not resolved["sign"]: return None
        return {"operation":"sign","signing_fingerprint":"".join(str(rule["signing_fingerprint"]).split()).upper()}
