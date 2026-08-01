# Outbound mail Phase B2 parameter discovery — 2026-08-01

## Purpose

The committed WW.CX website bridge permits exactly `https://edge1.ww.cx/outbound-mail/api/v1`. The Phase B2 hostname is therefore `edge1.ww.cx`; it is not inferred or newly selected by this tool.

The remaining proposal inputs are:

- the existing approved certificate full-chain path on Edge1;
- the corresponding existing private-key path, identified by metadata only;
- the actual outbound NAT address measured from business159 and expressed as one `/32` or `/128`.

An A record for the website is not sufficient proof of the shared host's outbound source address.

## Edge1 discovery command

```sh
cd /opt/edge1-management-interface
sudo sh tools/messaging/outbound_mail_phase_b2_parameter_discovery.sh
```

The script requires clean `main`, exact host `edge1.ww.cx`, active loopback B1 service, HTTP `401` for unsigned preparation, and HTTP `403` for send.

It inventories port 443, installed web services, public certificate metadata, and configured certificate path references. It does not read private-key contents. Private-key handling is limited to pathname, ownership, mode, size, type, and `contents_read=no` metadata.

Evidence is written to:

```text
/var/lib/wwcx-deployment-evidence/outbound-mail-phase-b2-parameter-discovery/<UTC timestamp>/
```

The generated `candidate-parameters.env` always leaves `PROPOSED_CLIENT_CIDR` as `BUSINESS159_EGRESS_MEASUREMENT_REQUIRED`. Certificate paths are populated only when one unambiguous public-certificate candidate and one existing private-key pathname candidate are found.

## business159 measurement

Run the separately reviewed website-repository tool on business159. It queries multiple HTTPS address-echo services, normalizes the results, and accepts a source candidate only when at least two independent services agree on one address.

The measured address must be converted to one exact IPv4 `/32` or IPv6 `/128`. Do not substitute a DNS A or AAAA record.

## Next safe step

After both evidence bundles are available, run the existing Phase B2 proposal-validation audit with all four exact values. That audit renders a candidate nginx configuration into restricted evidence only.

No live B2 change is performed by discovery or proposal validation. Proxy installation/reload, certificate/key-pair testing, DNS, firewall, public exposure, website bridge activation, provider/sender activation, delivery, and messages remain separate execution steps with rollback and validation.
