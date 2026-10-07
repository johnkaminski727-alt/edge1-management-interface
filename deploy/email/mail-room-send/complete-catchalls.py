#!/usr/bin/env python3
"""Configure approved shared domain catch-alls without sending mail."""
import json,os,shutil,sys
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[3]
def main():
    if os.geteuid()!=0 or sys.argv[1:]!=["--apply"]:raise SystemExit("root and --apply required")
    sys.path.insert(0,str(ROOT/"server"))
    import mail_identity_registry as registry
    p=Path("/etc/wwcx/outbound-mail/identities.json");r=json.loads(p.read_text())
    for domain in r["domains"]:
        address="contact@"+domain
        r.setdefault("catch_all_domains",{})[domain]={"default_sender":address,"delivery_mailbox":r["mailboxes"]["shared_role"]["address"]}
        key=next((k for k,v in r["sender_profiles"].items() if v["address"]==address),"catch-all-contact-"+domain)
        if key not in r["sender_profiles"]:
            r["sender_profiles"][key]={"address":address,"display_name":r["domains"][domain]["operating_name"],"organization":r["domains"][domain]["legal_name"],"use_for":"Default company catch-all correspondence","address_class":"work_role","status":"commissioned","outbound_enabled":True}
        r["sender_profiles"][key]["outbound_enabled"]=True
        r["sender_selection"]["recipient_to_sender"][address]=address
        if address not in r["sender_selection"]["live_sender_allowlist"]:r["sender_selection"]["live_sender_allowlist"].append(address)
    registry.validate_registry(r)
    for domain in r["domains"]:
        result=registry.resolve_sender(r,{"original_recipient":"commissioning-check@"+domain})
        if not result.live_enabled or result.address!="commissioning-check@"+domain:raise RuntimeError("Catch-all reply gate failed")
    if registry.resolve_sender(r,{"original_recipient":"john@ww.cx"}).address!="john@ww.cx":raise RuntimeError("Private John reply changed")
    stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    shutil.copy2(p,"/var/backups/mail-identities-before-catchalls-"+stamp+".json")
    p.write_text(json.dumps(r,indent=2)+"\n")
    print(json.dumps({"catch_all_domains":sorted(r["catch_all_domains"]),"private_john":"john@ww.cx","mail_sent":False}))
if __name__=="__main__":main()
