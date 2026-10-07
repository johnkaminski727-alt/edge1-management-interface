# WW.CX hidden-primary DNS commissioning

Public delegation remains on Dyn. Edge1 is intended to become a private hidden primary only after a complete Dyn Standard DNS zone export is imported and validated. AdGuard/Unbound recursion and WireGuard split DNS remain separate.

## Obtain the authoritative inventory

In the Dyn account: **My Zones/Domains → Dyn Standard DNS Service beside `ww.cx` → Export Zone → Save File**. Do not transcribe records manually.

Copy the exported text file to Edge1, then import it with:

```sh
sudo /opt/edge1-management-interface/tools/dns/import_dyn_standard_zone.py /path/to/export.txt --confirm-complete-dyn-export
sudo /opt/edge1-management-interface/tools/dns/validate_hidden_primary_candidate.py \
  --inventory /var/lib/edge1-authoritative-dns/ww.cx-inventory.json \
  --zone-file /var/lib/edge1-authoritative-dns/ww.cx.zone
```

The importer preserves the original Dyn export, creates a checksum-matched candidate zone and inventory manifest, and does not activate BIND, change public delegation, or change MX.

## Activation gates

Activation requires all of the following: complete exported zone inventory, validator success, explicit hidden-primary listen address, Dyn secondary-zone configuration, source-restricted TCP/UDP 53 firewall rules for Dyn transfer addresses, and post-transfer verification. Public NS delegation and MX changes remain separately gated.
