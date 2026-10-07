"""SCG-only Edge1 submission and fail-closed ClamAV scan."""
import hashlib
import smtplib
import socket
import struct
from datetime import datetime, timezone
import outbound_mail_gateway as gateway

SOCKET = "/run/wwcx-mail-clamd/scan.sock"
HOST = "127.0.0.1"
PORT = 10027

def scan(message_bytes):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(65)
        client.connect(SOCKET)
        client.sendall(b"zVERSION\0")
        version = client.recv(4096).rstrip(b"\0").decode()
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(65)
        client.connect(SOCKET)
        client.sendall(b"zINSTREAM\0")
        for offset in range(0, len(message_bytes), 65536):
            chunk = message_bytes[offset:offset+65536]
            client.sendall(struct.pack("!I",len(chunk))+chunk)
        client.sendall(struct.pack("!I",0))
        result = b""
        while b"\0" not in result and len(result) < 8192:
            part=client.recv(4096)
            if not part: break
            result += part
    clean = result.rstrip(b"\0") == b"stream: OK"
    return {"contract":"wwcx.mail-final-scan.v1", "state":"clean" if clean else "scan_error",
        "engine":"ClamAV", "engine_version":version, "ruleset_version":version,
        "message_sha256":hashlib.sha256(message_bytes).hexdigest(),
        "reason_codes":[] if clean else ["CLAMAV_NOT_CLEAN"]}

def submit(config, preview, message_bytes, message_id):
    profile=config["provider"]["profiles"][config["provider"]["selected"]]
    sender=preview["request"]["from_address"]
    if profile["type"] != "local_mta" or not profile["enabled"] or sender.rsplit("@",1)[-1] not in profile["allowed_from_domains"]:
        raise gateway.ProviderUnavailableError("sender is outside the commissioned local route")
    recipients=preview["request"]["recipients"]
    with smtplib.SMTP(HOST, PORT, timeout=65) as client:
        client.ehlo("gateway.edge1.ww.cx")
        refused=client.sendmail(sender,recipients,message_bytes)
    if refused: raise gateway.ProviderUnavailableError("local MTA refused recipients")
    return {"provider":config["provider"]["selected"],"provider_type":"local_mta",
        "message_id":message_id,"recipient_count":len(recipients),
        "submitted_at":datetime.now(timezone.utc).isoformat(timespec="seconds")}
