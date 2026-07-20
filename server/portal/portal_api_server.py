#!/usr/bin/env python3

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


BASE = Path(__file__).resolve().parents[2]

PORTAL = (
    BASE /
    "data/registry/interconnect/portal"
)


class Handler(BaseHTTPRequestHandler):

    def do_GET(self):

        if self.path == "/portal/status":

            self.send_json(
                "public-summary.json"
            )

            return


        if self.path == "/portal/carriers":

            self.send_json(
                "carrier-status.json"
            )

            return


        self.send_response(404)
        self.end_headers()


    def send_json(self, filename):

        path = PORTAL / filename

        body = path.read_bytes()

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


def main():

    server = HTTPServer(
        (
            "127.0.0.1",
            8098
        ),
        Handler
    )

    print(
        "Portal API listening on 8097"
    )

    server.serve_forever()


if __name__ == "__main__":
    main()
