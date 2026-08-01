#!/usr/bin/env python3
"""Provider-neutral policy and composition helpers for WW.CX outbound mail."""
from __future__ import annotations
import copy, hashlib, json, re, secrets
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote

CONTRACT="wwcx.outbound-mail-policy.v1"
FOOTER_MARKER="[WWCX-CORRESPONDENCE-CONTROL]"
PLACEHOLDER_ADDRESS="CONFIGURE_AT_DEPLOYMENT"
ALLOWED_MESSAGE_CLASSES={"business_correspondence","commercial","legal_notice","support"}
ALLOWED_PROVIDERS={"disabled","smtp_submission","gmail_api","microsoft_graph","manual_export"}
CONTROL_ID_RE=re.compile(r"^[A-Z0-9][A-Z0-9._:-]{5,127}$")
EMAIL_RE=re.compile(r"^[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+$")

def load_policy(path:str|Path)->dict[str,Any]: return json.loads(Path(path).read_text(encoding="utf-8"))
def _text(value:Any,label:str)->str:
    if not isinstance(value,str) or not value.strip(): raise ValueError(f"{label} must be non-empty text")
    return value.strip()
def _bool(value:Any,label:str)->None:
    if not isinstance(value,bool): raise ValueError(f"{label} must be boolean")
def _keys(value:Any,expected:set[str],label:str)->None:
    if not isinstance(value,dict): raise ValueError(f"{label} must be an object")
    if set(value)!=expected: raise ValueError(f"{label} keys invalid; missing={sorted(expected-set(value))}, unexpected={sorted(set(value)-expected)}")

def validate_policy(p:dict[str,Any])->None:
    _keys(p,{"contract","enabled","deployment_authorized","smtp_cutover_authorized","organization","footer","tracking","audit","delivery"},"policy")
    if p["contract"]!=CONTRACT: raise ValueError("unsupported policy contract")
    for k in ("enabled","deployment_authorized","smtp_cutover_authorized"): _bool(p[k],k)
    o=p["organization"]; _keys(o,{"legal_name","operating_name","website","privacy_url","contact_email","mailing_address"},"organization")
    for k in o: _text(o[k],f"organization.{k}")
    if not EMAIL_RE.fullmatch(o["contact_email"]): raise ValueError("organization.contact_email is invalid")
    f=p["footer"]; _keys(f,{"append_to_plain_text","append_to_html","include_confidentiality_notice","include_non_creation_caveat","include_action_link","include_tracking_disclosure","require_unsubscribe_for_commercial"},"footer")
    for k,v in f.items(): _bool(v,f"footer.{k}")
    t=p["tracking"]; _keys(t,{"action_base_url","transparent_action_links","hidden_open_tracking","device_fingerprinting","collect_full_ip","ip_storage_mode","retention_days"},"tracking")
    _text(t["action_base_url"],"tracking.action_base_url")
    for k in ("transparent_action_links","hidden_open_tracking","device_fingerprinting","collect_full_ip"): _bool(t[k],f"tracking.{k}")
    if t["hidden_open_tracking"] or t["device_fingerprinting"] or t["collect_full_ip"]: raise ValueError("covert tracking, fingerprinting, and full IP storage are prohibited")
    if t["ip_storage_mode"] not in {"none","truncated","keyed_hash"}: raise ValueError("unsupported IP storage mode")
    if not isinstance(t["retention_days"],int) or not 1<=t["retention_days"]<=730: raise ValueError("tracking.retention_days must be between 1 and 730")
    a=p["audit"]; _keys(a,{"write_jsonl","record_recipient_addresses","record_body","record_action_token","record_action_token_hash"},"audit")
    for k,v in a.items(): _bool(v,f"audit.{k}")
    if a["record_body"] or a["record_action_token"] or not a["record_action_token_hash"]: raise ValueError("audit policy would retain prohibited content")
    d=p["delivery"]; _keys(d,{"provider","allow_prepare","allow_external_submission","allow_live_delivery","allowed_from_domains","max_recipients","message_size_limit_bytes"},"delivery")
    if d["provider"] not in ALLOWED_PROVIDERS: raise ValueError("delivery.provider is unsupported")
    for k in ("allow_prepare","allow_external_submission","allow_live_delivery"): _bool(d[k],f"delivery.{k}")
    if not isinstance(d["allowed_from_domains"],list) or not d["allowed_from_domains"]: raise ValueError("allowed_from_domains must be non-empty")
    if not isinstance(d["max_recipients"],int) or not 1<=d["max_recipients"]<=500: raise ValueError("invalid max_recipients")
    if not isinstance(d["message_size_limit_bytes"],int) or not 1024<=d["message_size_limit_bytes"]<=10485760: raise ValueError("invalid message size limit")
    if p["enabled"] and not p["deployment_authorized"]: raise ValueError("enabled policy requires deployment authorization")
    if d["allow_external_submission"] and not p["enabled"]: raise ValueError("external submission requires an enabled policy")
    if d["allow_live_delivery"]:
        if not (p["enabled"] and p["deployment_authorized"] and p["smtp_cutover_authorized"]): raise ValueError("live delivery requires all cutover gates")
        if d["provider"] in {"disabled","manual_export"}: raise ValueError("live delivery requires a delivery provider")
        if o["mailing_address"]==PLACEHOLDER_ADDRESS: raise ValueError("live delivery requires a mailing address")
    if f["include_action_link"] and (not t["transparent_action_links"] or not f["include_tracking_disclosure"]): raise ValueError("action links require disclosure")

def normalize_recipients(values:Iterable[str],max_count:int=500)->list[str]:
    result=sorted({_text(v,"recipient").casefold() for v in values})
    if not result or len(result)>max_count or any(not EMAIL_RE.fullmatch(v) or "\r" in v or "\n" in v for v in result): raise ValueError("recipient address or count is invalid")
    return result

def validate_from_address(p:dict[str,Any],value:str)->str:
    validate_policy(p); address=_text(value,"from_address").casefold()
    if not EMAIL_RE.fullmatch(address) or address.rsplit("@",1)[1] not in {str(x).casefold() for x in p["delivery"]["allowed_from_domains"]}: raise ValueError("from_address domain is not allowed")
    return address

def generate_action_token(byte_count:int=32)->tuple[str,str]:
    if not 16<=byte_count<=64: raise ValueError("byte_count must be between 16 and 64")
    token=secrets.token_urlsafe(byte_count); return token,hashlib.sha256(token.encode()).hexdigest()
def build_action_url(base_url:str,token:str)->str: return _text(base_url,"base_url").rstrip("/")+"/"+quote(_text(token,"token"),safe="")
def derive_control_id(subject:str,recipients:Iterable[str],namespace:str="WWCX",now:datetime|None=None)->str:
    when=now or datetime.now(timezone.utc); material=json.dumps([_text(subject,"subject"),normalize_recipients(recipients),when.isoformat()],separators=(",",":"),sort_keys=True)
    return f"{namespace}-{when:%Y%m%dT%H%M%SZ}-{hashlib.sha256(material.encode()).hexdigest()[:12].upper()}"
def _control(value:str,label:str)->str:
    value=_text(value,label)
    if not CONTROL_ID_RE.fullmatch(value): raise ValueError(f"{label} contains unsupported characters")
    return value
def build_control_headers(*,control_id:str,case_id:str|None=None,action_id:str|None=None,policy_contract:str=CONTRACT)->dict[str,str]:
    h={"X-WWCX-Control-ID":_control(control_id,"control_id"),"X-WWCX-Policy":_text(policy_contract,"policy_contract"),"X-WWCX-Tracking":"disclosed-action-link; no-hidden-pixel"}
    if case_id: h["X-WWCX-Case-ID"]=_control(case_id,"case_id")
    if action_id: h["X-WWCX-Action-ID"]=_control(action_id,"action_id")
    if any("\r" in v or "\n" in v for v in h.values()): raise ValueError("unsafe header value")
    return h

def render_plain_text_footer(p:dict[str,Any],*,message_class:str,signer_name:str,signer_title:str,control_id:str,action_url:str|None,unsubscribe_url:str|None=None)->str:
    validate_policy(p)
    if message_class not in ALLOWED_MESSAGE_CLASSES: raise ValueError("unsupported message class")
    if message_class=="commercial" and p["footer"]["require_unsubscribe_for_commercial"]: _text(unsubscribe_url,"unsubscribe_url")
    o=p["organization"]; lines=["--",_text(signer_name,"signer_name"),_text(signer_title,"signer_title"),f"{o['operating_name']} | {o['legal_name']}",o["mailing_address"],f"Email: {o['contact_email']} | Web: {o['website']}","",FOOTER_MARKER,f"Correspondence control: {_control(control_id,'control_id')}"]
    if p["footer"]["include_action_link"]: lines.append("View the correspondence record or acknowledge receipt: "+_text(action_url,"action_url"))
    if p["footer"]["include_tracking_disclosure"]: lines += ["Access to the linked correspondence record may be logged for security, delivery verification, records management, and dispute resolution.",f"Privacy information: {o['privacy_url']}"]
    if p["footer"]["include_confidentiality_notice"]: lines += ["","CONFIDENTIALITY AND RECORDS NOTICE: This message and any attachments may contain confidential information intended for the addressed recipient. If received in error, notify the sender and delete the material."]
    if p["footer"]["include_non_creation_caveat"]: lines.append("This notice does not create confidentiality, privilege, a contractual duty, or other legal rights where they do not otherwise exist.")
    if message_class=="commercial" and unsubscribe_url: lines += ["",f"Commercial-message preferences or unsubscribe: {unsubscribe_url}"]
    return "\n".join(lines).rstrip()+"\n"
def render_html_footer(p:dict[str,Any],**kwargs:Any)->str:
    return '<div data-wwcx-correspondence-control="1" style="margin-top:24px;border-top:1px solid #bbb;padding-top:14px;font-family:Arial,sans-serif;font-size:12px;line-height:1.45;color:#444">'+"<br>".join(escape(x) for x in render_plain_text_footer(p,**kwargs).rstrip().split("\n"))+"</div>"
def append_plain_text_footer(body:str,footer:str)->str:
    body=body.rstrip(); return body+"\n" if FOOTER_MARKER in body else (body+"\n\n"+footer if body else footer)
def append_html_footer(body:str,footer:str)->str: return body if 'data-wwcx-correspondence-control="1"' in body else body.rstrip()+footer

def compose_message(p:dict[str,Any],*,body:str,subject:str,recipients:Iterable[str],from_address:str,signer_name:str,signer_title:str,message_class:str="business_correspondence",body_html:str|None=None,control_id:str|None=None,case_id:str|None=None,action_id:str|None=None,unsubscribe_url:str|None=None,timestamp:datetime|None=None)->dict[str,Any]:
    validate_policy(p)
    if not p["delivery"]["allow_prepare"]: raise ValueError("message preparation is disabled")
    when=timestamp or datetime.now(timezone.utc); recipients=normalize_recipients(recipients,p["delivery"]["max_recipients"]); from_address=validate_from_address(p,from_address); control_id=control_id or derive_control_id(subject,recipients,now=when); token,token_hash=generate_action_token(); action_url=build_action_url(p["tracking"]["action_base_url"],token)
    kw=dict(message_class=message_class,signer_name=signer_name,signer_title=signer_title,control_id=control_id,action_url=action_url,unsubscribe_url=unsubscribe_url)
    plain=append_plain_text_footer(body,render_plain_text_footer(p,**kw)); html=None if body_html is None else append_html_footer(body_html,render_html_footer(p,**kw))
    if len(plain.encode())+len((html or "").encode())>p["delivery"]["message_size_limit_bytes"]: raise ValueError("prepared message exceeds size limit")
    audit={"event":"outbound_message_prepared","occurred_at":when.isoformat(timespec="seconds"),"control_id":_control(control_id,"control_id"),"message_class":message_class,"subject_sha256":hashlib.sha256(_text(subject,"subject").encode()).hexdigest(),"body_sha256":hashlib.sha256(body.encode()).hexdigest(),"recipient_count":len(recipients),"from_address":from_address,"action_token_sha256":token_hash,"policy_contract":CONTRACT,"delivery_provider":p["delivery"]["provider"],"live_delivery_authorized":p["delivery"]["allow_live_delivery"]}
    if p["audit"]["record_recipient_addresses"]: audit["recipients"]=recipients
    if case_id: audit["case_id"]=_control(case_id,"case_id")
    if action_id: audit["action_id"]=_control(action_id,"action_id")
    return {"body":plain,"html_body":html,"headers":build_control_headers(control_id=control_id,case_id=case_id,action_id=action_id),"control_id":control_id,"action_url":action_url,"action_token":token,"action_token_sha256":token_hash,"from_address":from_address,"recipients":recipients,"audit_record":audit,"delivery":{"provider":p["delivery"]["provider"],"live_delivery_authorized":p["delivery"]["allow_live_delivery"],"status":"prepared_not_sent"}}
def compose_plain_text_message(p:dict[str,Any],**kwargs:Any)->dict[str,Any]: return compose_message(p,from_address=p["organization"]["contact_email"],**kwargs)
def activated_prepare_only_copy(p:dict[str,Any],mailing_address:str)->dict[str,Any]:
    c=copy.deepcopy(p); c["enabled"]=True; c["deployment_authorized"]=True; c["organization"]["mailing_address"]=_text(mailing_address,"mailing_address"); c["delivery"].update(provider="manual_export",allow_prepare=True,allow_external_submission=True,allow_live_delivery=False); validate_policy(c); return c
def activated_copy(p:dict[str,Any],mailing_address:str)->dict[str,Any]:
    c=activated_prepare_only_copy(p,mailing_address); c["smtp_cutover_authorized"]=True; c["delivery"].update(provider="smtp_submission",allow_live_delivery=True); validate_policy(c); return c
