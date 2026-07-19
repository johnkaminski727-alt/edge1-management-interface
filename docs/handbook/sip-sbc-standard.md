# SIP and SBC Engineering Standard

Status: baseline standard

## Purpose

Define the minimum engineering controls for WW.CX SIP interconnection, session border control, routing, and troubleshooting.

## Design principles

- All untrusted or carrier-facing SIP traffic terminates on an SBC boundary before reaching PBX or application systems.
- Separate signalling, media, management, and monitoring planes where practical.
- Deny by default. Permit only documented peers, transports, codecs,