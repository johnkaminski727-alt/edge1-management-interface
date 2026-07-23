#!/usr/bin/env python3

import time
import json
import hmac
import hashlib
import urllib.request

CLIENT = "shared-hosting-portal"

with open("config/portal/client-credentials.json") as f:
    secret = json.load(f)["clients"][CLIENT]["secret"]

def request(path):

    timestamp = str(int(time.time()))

    payload = (
        CLIENT +
        timestamp
    ).encode()

    signature = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()

    req = urllib.request.Request(
        "http://127.0.0.1:8097" + path,
        headers={
            "X-Portal-Client": CLIENT,
            "X-Portal-Timestamp": timestamp,
            "X-Portal-Signature": signature
        }
    )

    try:
        with urllib.request.urlopen(req) as r:
            print(path, r.status)
            print(r.read().decode())
            print()

    except Exception as e:
        print(path, e)
        print()


for endpoint in [
    "/portal/status",
    "/portal/carriers",
    "/portal/interconnects",
    "/portal/numbers",
    "/portal/health",
]:
    request(endpoint)
