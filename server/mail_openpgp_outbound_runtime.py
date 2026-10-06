#!/usr/bin/env python3
from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Any
import mail_openpgp_policy
CONTRACT = "wwcx.openpgp-outbound-senders.v1"
DEFAULT_POLICY = Path("/etc/wwcx/outbound-mail/openpgp-policy.json")
DEFAULT_SENDERS = Path("/etc/wwcx/outbound-mail/openpgp-senders.json")
DEFAULT_RECIPIENTS = Path("/etc/wwcx/outbound-mail/openpgp-recipient-keys.json")
RECIPIENT_CONTRACT = "wwcx.openpgp-recipient-keys.v1"
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

def validate_recipients(data: dict[str, Any]) -> dict[str, Any]:
    if data.get("contract") != RECIPIENT_CONTRACT:
        raise OpenPGPOutboundRuntimeError("unsupported OpenPGP recipient contract")
    if data.get("private_key_material_included") is not False or data.get("armored_public_key_material_included") is not False:
        raise OpenPGPOutboundRuntimeError("OpenPGP recipient map contains prohibited material")
    recipients=data.get("recipients")
    if not isinstance(recipients,dict): raise OpenPGPOutboundRuntimeError("OpenPGP recipient map is invalid")
    return data

class RuntimeOpenPGPResolver:
    def __init__(self,policy_path: str|Path=DEFAULT_POLICY,senders_path: str|Path=DEFAULT_SENDERS,recipients_path: str|Path=DEFAULT_RECIPIENTS):
        self.policy_path=Path(policy_path); self.senders_path=Path(senders_path); self.recipients_path=Path(recipients_path)
    def __call__(self,request: dict[str,Any]) -> dict[str,Any]|None:
        if not isinstance(request,dict): raise OpenPGPOutboundRuntimeError("outbound request is invalid")
        sender=str(request.get("from_address","")).strip().casefold(); recipients=request.get("recipients")
        if not sender or not isinstance(recipients,list) or not recipients: raise OpenPGPOutboundRuntimeError("outbound OpenPGP request is incomplete")
        senders=validate_senders(_load(self.senders_path)); rule=senders["senders"].get(sender)
        if rule is None: return None
        policy=mail_openpgp_policy.validate_policy(_load(self.policy_path))
        if policy.get("enabled") is not True or policy.get("deployment_authorized") is not True: raise OpenPGPOutboundRuntimeError("OpenPGP mail policy is not authorized")
        mode=str(rule["mode"])
        recipient_keys=[]
        if mode not in {"disabled","sign_only"}:
            registry=validate_recipients(_load(self.recipients_path))["recipients"]
            now=int(time.time())
            for address in recipients:
                item=registry.get(str(address).casefold())
                if not item:
                    continue
                subkeys=item.get("encryption_subkeys") or []
                expired=not any(x.get("expires_unix") is None or int(x["expires_unix"])>now for x in subkeys if isinstance(x,dict))
                recipient_keys.append(mail_openpgp_policy.RecipientKey(address=str(address).casefold(),fingerprint=str(item.get("primary_fingerprint",'')),verified=item.get("verification_status")=='verified',expired=expired))
        resolved=mail_openpgp_policy.resolve_mode(policy,mode,recipient_keys,len(recipients))
        signing_fp="".join(str(rule["signing_fingerprint"]).split()).upper()
        if resolved["encrypt"]:
            return {"operation":"sign_encrypt" if resolved["sign"] else "encrypt","signing_fingerprint":signing_fp if resolved["sign"] else None,"recipient_fingerprints":resolved["fingerprints"]}
        if not resolved["sign"]: return None
        return {"operation":"sign","signing_fingerprint":signing_fp}
