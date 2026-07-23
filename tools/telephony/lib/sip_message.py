#!/usr/bin/env python3

from datetime import datetime


def build_options_request(host, port=5060):

    branch = "z9hG4bK-edge1"

    return (
        f"OPTIONS sip:{host}:{port} SIP/2.0\r\n"
        f"Via: SIP/2.0/UDP {host}:{port};branch={branch}\r\n"
        f"From: <sip:edge1@localhost>;tag=edge1\r\n"
        f"To: <sip:{host}>\r\n"
        f"Call-ID: edge1-options-{datetime.utcnow().timestamp()}\r\n"
        f"CSeq: 1 OPTIONS\r\n"
        f"Max-Forwards: 70\r\n"
        f"Content-Length: 0\r\n"
        f"\r\n"
    )


def parse_response(response):

    lines = response.splitlines()

    if not lines:
        return {
            "status": "invalid"
        }

    first = lines[0]

    parts = first.split()

    if len(parts) < 3:
        return {
            "status": "invalid"
        }

    return {
        "protocol": parts[0],
        "code": int(parts[1]),
        "reason": " ".join(parts[2:])
    }
