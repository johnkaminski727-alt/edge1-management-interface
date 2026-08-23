"""Bounded HMAC client for account-owned VPN enrollment and registration state."""
from __future__ import annotations
import hashlib, hmac, json, secrets, time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

class VPNAccountBackendError(Exception): pass

class VPNAccountBackend:
    def __init__(self, secret_path: Path, timeout_seconds: int = 10):
        self.secret_path=secret_path; self.timeout_seconds=timeout_seconds
    def _secret(self):
        if self.secret_path.is_symlink(): raise VPNAccountBackendError("secret path invalid")
        value=self.secret_path.read_bytes().strip()
        if len(value)<32: raise VPNAccountBackendError("secret invalid")
        return value
    def _request(self, base: str, method: str, path: str, subject: str, payload=None):
        if base not in ("http://127.0.0.1:8790", "http://127.0.0.1:8097"):
            raise VPNAccountBackendError("backend origin invalid")
        actor="edge1-vpn-account:"+subject
        body=b"" if payload is None else json.dumps(payload,separators=(",",":"),sort_keys=True).encode()
        ts=str(int(time.time())); nonce=secrets.token_hex(24); body_hash=hashlib.sha256(body).hexdigest()
        canonical="\n".join((method,path,ts,nonce,actor,body_hash)).encode()
        sig=hmac.new(self._secret(),canonical,hashlib.sha256).hexdigest()
        headers={"Accept":"application/json","X-WWCX-Actor":actor,"X-WWCX-Timestamp":ts,"X-WWCX-Nonce":nonce,"X-WWCX-Signature":sig}
        if payload is not None: headers["Content-Type"]="application/json"
        req=Request(base+path,data=None if payload is None else body,method=method,headers=headers)
        try:
            with urlopen(req,timeout=self.timeout_seconds) as response:
                raw=response.read(131073); status=response.status
        except HTTPError as exc:
            raw=exc.read(131073); status=exc.code
        except (URLError,TimeoutError,OSError) as exc:
            raise VPNAccountBackendError("backend unavailable") from exc
        if len(raw)>131072: raise VPNAccountBackendError("backend response too large")
        try: data=json.loads(raw or b"{}")
        except Exception as exc: raise VPNAccountBackendError("backend response invalid") from exc
        if status!=200 or not isinstance(data,dict):
            raise VPNAccountBackendError(str(data.get("error","backend request failed")) if isinstance(data,dict) else "backend request failed")
        return data
    def enrollment(self, subject: str, action: str, parameters: dict):
        data=self._request("http://127.0.0.1:8790","POST","/internal/account",subject,{"action":action,"parameters":parameters})
        return data.get("result",{})
    def registration_devices(self, subject: str):
        return self._request("http://127.0.0.1:8097","GET","/v1/vpn-access/devices",subject).get("devices",[])
    def policies(self, subject: str):
        return self._request("http://127.0.0.1:8097","GET","/v1/vpn-access/policies",subject).get("policies",[])
    def accept_policy(self, subject: str, device_id: str, policy_version=None):
        payload={"device_id":device_id,"source":"wwcx-account"}
        if policy_version: payload["policy_version"]=policy_version
        data=self._request("http://127.0.0.1:8097","POST","/v1/vpn-access/acceptances",subject,payload)
        return data.get("result",{})
