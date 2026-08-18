# Project Big Bird bounded camera LAN discovery

Status: repository candidate; not deployed.

This one-shot helper advances M2 without broad scanning or public exposure. Default behavior reads only the local kernel neighbor table and writes private evidence under `/var/lib/bigbird-camera/discovery` with restrictive permissions. It does not identify a WFCAMOUT merely because a host exists.

Optional active probing is deliberately narrow: one explicit non-loopback private/link-local address, only after that address is already present in the local neighbor table, and only fixed TCP ports 80, 443, and 554. It does not scan subnets, arbitrary ports, or the Internet.

Private IP/MAC observations remain only in the private evidence file. Standard output contains counts, an evidence hash/path, and any open allowlisted port numbers, but no private identifiers.

This tool is discovery evidence only. It does not provision a camera, obtain BAZZ/Tuya credentials, generate a QR code, infer WFCAMOUT protocol support, or claim M2/M3 acceptance.
