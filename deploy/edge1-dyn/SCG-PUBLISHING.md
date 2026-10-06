# Spirit Creek Gardens DNS publishing

Edge1 stores desired records in `/var/lib/edge1-dyn/zones/spiritcreekgardens.com.json`.
Dyn remains the public authoritative provider. This is a private desired-state
publisher using TSIG, not a BIND hidden-primary/AXFR secondary deployment.
WireGuard private DNS and recursive resolvers are independent.

`edge1-scg-dns-publish.timer` runs every five minutes. It verifies the mail A,
SPF, DKIM and DMARC records on all four Dyn nameservers and restores missing
values using the existing root-only account TSIG key. Conflicting values cause
failure and require review. Existing TXT verification records are preserved.
No deletion, replacement, website rewrite or MX cutover is automated.

Status and audit: `/var/lib/edge1-dyn/scg-status.json` and `scg-audit.jsonl`.
Disable writes by setting `automatic_publish` to false in the desired-state file;
the scheduled check continues in read-only mode. Disable the timer to stop checks.
TSIG probe add and exact-value deletion passed on all four nameservers on
2026-10-06. Mail A/SPF/DKIM/DMARC all matched at commissioning.

The ww.cx publisher is unchanged. Its commissioning remains a separate task.
