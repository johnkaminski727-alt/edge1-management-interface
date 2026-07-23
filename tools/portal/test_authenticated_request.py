#!/usr/bin/env python3

import json
import time
import hmac
import hashlib
import urllib.request


CLIENT = "shared-hosting-portal"

CREDS = "config/portal/client-credentials.json"

URL = "http://127.0.0.1:8097/portal/status"


with open(CREDS) as f:
    creds = json.load(f)

secret = creds["clients"][CLIENT]["secret"]

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
    URL,
    headers={
        "X-Portal-Client": CLIENT,
        "X-Portal-Timestamp": timestamp,
        "X-Portal-Signature": signature,
    },
)


try:
    with urllib.request.urlopen(req) as response:
        print("HTTP:", response.status)
        print(response.read().decode())

except Exception as e:
    print("FAILED:", e)
