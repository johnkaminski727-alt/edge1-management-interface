import hashlib
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from .models import (
    Channel,
    CoordinateAttestation,
    Direction,
    MediaItem,
    NormalizedMessage,
    SecurityAttestation,
    SecurityMode,
    TimeAttestation,
    VerificationEnvelope,
)


class TelegraphDispatchRequest(BaseModel):
    sender: str = Field(min_length=1, max_length=255)
    recipients: list[str] = Field(min_length=1)
    channel: Channel = Channel.SMS
    text: str = Field(default="", max_length=20000)
    media: list[MediaItem] = Field(default_factory=list)
    coordinates: CoordinateAttestation | None = None
    client_observed_at_utc: datetime | None = None
    security_mode: SecurityMode = SecurityMode.PLAIN
    recipient_fingerprints: list[str] = Field(default_factory=list)
    signer_fingerprint: str | None = None
    ciphertext_armored: str | None = Field(default=None, max_length=200000)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _page() -> str:
    return r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Spirit Creek Telegraph Office</title>
<style>
:root{color-scheme:dark;background:#17110b;color:#f4dfb0;font-family:Georgia,serif}
body{margin:0;background:linear-gradient(#24170d,#100b07);min-height:100vh}
main{max-width:980px;margin:auto;padding:24px}.sign{text-align:center;border:4px double #c69551;padding:18px;background:#2b1a0d;box-shadow:0 8px 30px #000}
.window{margin-top:20px;border:12px solid #5c351b;background:#d6b77a;color:#25160c;padding:20px;box-shadow:inset 0 0 30px #6a431f}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}.wide{grid-column:1/-1}label{display:block;font-weight:bold;margin-bottom:5px}input,select,textarea,button{width:100%;box-sizing:border-box;padding:10px;border:2px solid #68421f;background:#fff8df;color:#21150c;font:inherit}textarea{min-height:120px}button{cursor:pointer;background:#5b2f16;color:#fff0c8;font-weight:bold}.options{display:flex;gap:16px;flex-wrap:wrap}.options label{font-weight:normal}.options input{width:auto}.receipt{white-space:pre-wrap;background:#17110b;color:#d9efc8;padding:16px;margin-top:18px;min-height:80px}.small{font-size:.9rem}.hidden{display:none}@media(max-width:700px){.grid{grid-template-columns:1fr}.wide{grid-column:auto}}
</style>
</head>
<body><main>
<section class="sign"><h1>SPIRIT CREEK TELEGRAPH OFFICE</h1><div>Messages dispatched by wire, bridge, and gateway</div></section>
<section class="window">
<form id="dispatch">
<div class="grid">
<div><label>Simulator token</label><input id="token" type="password" autocomplete="off" required></div>
<div><label>Preset</label><select id="preset"><option>Custom Dispatch</option><option>Gateway Test</option><option>Appointment Reminder</option><option>Community Notice</option></select></div>
<div><label>From</label><input id="sender" value="Spirit Creek Telegraph Office" required></div>
<div><label>To</label><input id="recipient" value="+15550100001" required></div>
<div><label>Service</label><select id="channel"><option value="sms">SMS</option><option value="mms">MMS</option></select></div>
<div><label>Security</label><select id="security"><option value="plain">Plain</option><option value="signed">PGP signed metadata</option><option value="encrypted">PGP armored ciphertext</option><option value="encrypted_and_signed">PGP encrypted + signed metadata</option></select></div>
<div class="wide"><label>Message or armored ciphertext</label><textarea id="message" required>Yee Haw! Test telegram from the Spirit Creek Telegraph Office.</textarea></div>
<div><label>Recipient key fingerprint</label><input id="recipientFingerprint" placeholder="Optional"></div>
<div><label>Signer fingerprint</label><input id="signerFingerprint" placeholder="Optional"></div>
<div class="wide options"><label><input id="location" type="checkbox"> Attach present coordinates</label><label><input id="copyReplies" type="checkbox" checked> Route incoming replies to dispatch desk</label></div>
<div class="wide"><button type="submit">DISPATCH TELEGRAM</button></div>
</div>
</form>
<div class="small">Private keys and passphrases are never requested by this simulator window. Encrypt or decrypt locally, then paste only the armored payload. Location collection requires the checkbox and browser permission.</div>
<pre class="receipt" id="receipt">Awaiting operator dispatch.</pre>
</section>
</main>
<script>
const form=document.getElementById('dispatch');
const receipt=document.getElementById('receipt');
function position(){return new Promise((resolve,reject)=>navigator.geolocation.getCurrentPosition(resolve,reject,{enableHighAccuracy:true,timeout:10000,maximumAge:0}))}
form.addEventListener('submit',async(e)=>{
 e.preventDefault(); receipt.textContent='Preparing dispatch...';
 let coordinates=null;
 if(document.getElementById('location').checked){
  try{const p=await position();coordinates={latitude:p.coords.latitude,longitude:p.coords.longitude,accuracy_m:p.coords.accuracy,altitude_m:p.coords.altitude,altitude_accuracy_m:p.coords.altitudeAccuracy,source:'browser',observed_at:new Date(p.timestamp).toISOString(),consent:true,station_name:'Spirit Creek Operator Console'}}
  catch(err){receipt.textContent='Location verification failed: '+err.message;return}
 }
 const security=document.getElementById('security').value;
 const text=document.getElementById('message').value;
 const payload={sender:document.getElementById('sender').value,recipients:[document.getElementById('recipient').value],channel:document.getElementById('channel').value,text:text,media:[],coordinates:coordinates,client_observed_at_utc:new Date().toISOString(),security_mode:security,recipient_fingerprints:document.getElementById('recipientFingerprint').value?[document.getElementById('recipientFingerprint').value]:[],signer_fingerprint:document.getElementById('signerFingerprint').value||null,ciphertext_armored:security.includes('encrypted')?text:null};
 try{const r=await fetch('/v1/telegraph/dispatch',{method:'POST',headers:{'Content-Type':'application/json','X-WWCX-Simulator-Token':document.getElementById('token').value},body:JSON.stringify(payload)});const data=await r.json();if(!r.ok)throw new Error(data.detail||r.statusText);receipt.textContent='SPIRIT CREEK DISPATCH RECEIPT\n\n'+JSON.stringify(data,null,2)}catch(err){receipt.textContent='Dispatch failed: '+err.message}
});
</script></body></html>'''


def build_router(store, simulator_token_getter) -> APIRouter:
    router = APIRouter()

    @router.get("/telegraph-office", response_class=HTMLResponse)
    def telegraph_office() -> str:
        return _page()

    @router.post("/v1/telegraph/dispatch", status_code=status.HTTP_202_ACCEPTED)
    def dispatch(
        request: TelegraphDispatchRequest,
        x_wwcx_simulator_token: str | None = Header(default=None),
    ) -> dict[str, object]:
        if x_wwcx_simulator_token != simulator_token_getter():
            raise HTTPException(status_code=401, detail="invalid simulator token")
        if store.get_control_state()["paused"]:
            raise HTTPException(status_code=503, detail="messaging intake is paused")

        body = request.ciphertext_armored or request.text
        event_id = uuid4()
        now = datetime.now(timezone.utc)
        envelope = VerificationEnvelope(
            content_sha256=_digest(body),
            media_sha256=[item.sha256 for item in request.media if item.sha256],
            time=TimeAttestation(
                server_observed_at_utc=now,
                client_observed_at_utc=request.client_observed_at_utc,
                timezone="UTC",
            ),
            coordinates=request.coordinates,
            security=SecurityAttestation(
                mode=request.security_mode,
                recipient_fingerprints=request.recipient_fingerprints,
                signer_fingerprint=request.signer_fingerprint,
                plaintext_retained=False,
            ),
        )
        message = NormalizedMessage(
            event_id=event_id,
            provider="spirit-creek-simulator",
            provider_event_id=f"telegraph-{event_id}",
            direction=Direction.OUTBOUND,
            channel=request.channel,
            **{"from": request.sender, "to": request.recipients},
            text=body,
            media=request.media,
            occurred_at=now,
            verification=envelope,
        )
        accepted = store.put_if_absent(message)
        return {
            "accepted": accepted,
            "duplicate": not accepted,
            "event_id": str(event_id),
            "channel": request.channel,
            "security_mode": request.security_mode,
            "content_sha256": envelope.content_sha256,
            "server_observed_at_utc": now.isoformat(),
            "coordinates_attached": request.coordinates is not None,
            "storage": "simulator-ledger",
        }

    @router.get("/v1/telegraph/ledger")
    def ledger(
        x_wwcx_simulator_token: str | None = Header(default=None),
    ) -> dict[str, object]:
        if x_wwcx_simulator_token != simulator_token_getter():
            raise HTTPException(status_code=401, detail="invalid simulator token")
        list_recent = getattr(store, "list_recent", None)
        if not callable(list_recent):
            raise HTTPException(status_code=501, detail="ledger unavailable for configured store")
        return {
            "events": [
                {
                    "event_id": str(item.event_id),
                    "provider_event_id": item.provider_event_id,
                    "direction": item.direction,
                    "channel": item.channel,
                    "from": item.sender,
                    "to": item.recipients,
                    "occurred_at": item.occurred_at,
                    "verification": item.verification.model_dump(mode="json") if item.verification else None,
                }
                for item in list_recent()
            ]
        }

    return router
