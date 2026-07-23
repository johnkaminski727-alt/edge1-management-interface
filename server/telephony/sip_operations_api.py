#!/usr/bin/env python3

import json
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer


BASE = Path(__file__).resolve().parents[2]

STATUS_FILE = (
    BASE /
    "data/registry/interconnect/status/peer-status.json"
)

HISTORY_FILE = (
    BASE /
    "data/registry/interconnect/status/sip-options-history.json"
)

REGISTRY_FILE = (
    BASE /
    "data/registry/interconnect/interconnect-registry.json"
)


def load_json(path):

    if not path.exists():
        return {}

    with open(path) as f:
        return json.load(f)


class Handler(BaseHTTPRequestHandler):

    def send_json(self, data):

        body = json.dumps(
            data,
            indent=2
        ).encode()

        self.send_response(200)
        self.send_header(
            "Content-Type",
            "application/json"
        )
        self.send_header(
            "Content-Length",
            str(len(body))
        )
        self.end_headers()
        self.wfile.write(body)


    def do_GET(self):

        if self.path == "/telephony/status":

            self.send_json(
                load_json(STATUS_FILE)
            )

        elif self.path == "/telephony/health/history":

            self.send_json(
                load_json(HISTORY_FILE)
            )

        elif self.path == "/telephony/interconnects":

            self.send_json(
                load_json(REGISTRY_FILE)
            )

        else:

            self.send_response(404)
            self.end_headers()


def main():

    server = HTTPServer(
        (
            "127.0.0.1",
            8095
        ),
        Handler
    )

    print(
        "SIP Operations API listening on 8095"
    )

    server.serve_forever()


if __name__ == "__main__":
    main()
