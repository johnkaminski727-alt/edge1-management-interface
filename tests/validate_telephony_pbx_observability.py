#!/usr/bin/env python3
"""Validate privacy-minimized PBX/PJSIP aggregate parsing."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

import telephony_status_server as telephony

channels = """4 active channels\n2 active calls\n81 calls processed\n"""
assert telephony._asterisk_counter(channels, "active channels") == 4
assert telephony._asterisk_counter(channels, "active calls") == 2
assert telephony._asterisk_counter(channels, "calls processed") == 81
assert telephony._asterisk_counter("", "active calls") == 0

endpoints = """Endpoint: alpha Not in use 0 of inf\nEndpoint: beta Unavailable 0 of inf\nObjects found: 2\n"""
contacts = """Contact: alpha/sip:opaque-a Avail 12.0\nObjects found: 1\n"""
registrations = """Objects found: 3\n"""
transports = """Transport: transport-udp udp 0 0 0.0.0.0:5060\nObjects found: 1\n"""
assert telephony._pjsip_object_count(endpoints, "Endpoint") == 2
assert telephony._pjsip_object_count(contacts, "Contact") == 1
assert telephony._pjsip_object_count(registrations, "Registration") == 3
assert telephony._pjsip_object_count(transports, "Transport") == 1
assert telephony._pjsip_object_count("Endpoint: one\nEndpoint: two\n", "Endpoint") == 2

allowed = set(telephony.ASTERISK_READ_ONLY_COMMANDS.values())
assert allowed == {
    "core show channels count",
    "pjsip show endpoints",
    "pjsip show contacts",
    "pjsip show registrations",
    "pjsip show transports",
}

try:
    telephony._asterisk_cli("channel originate PJSIP/example application Echo")
except ValueError:
    pass
else:
    raise AssertionError("arbitrary Asterisk CLI command was not rejected")

server_source = (ROOT / "server" / "telephony_status_server.py").read_text(encoding="utf-8")
for marker in (
    '"pbx_endpoints"',
    '"pbx_contacts"',
    '"pbx_outbound_registrations"',
    '"pbx_transports"',
    '"read_only_cli_available"',
):
    assert marker in server_source

for prohibited in ("channel originate", "dialplan reload", "pjsip send register", "module reload"):
    assert prohibited not in server_source

print("Telephony PBX observability validation passed")
print("Only fixed read-only aggregate Asterisk/PJSIP commands are permitted")
