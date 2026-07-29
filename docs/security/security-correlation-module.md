# WW.CX Security Correlation Module

## Purpose

The module creates a privacy-preserving, read-only investigation snapshot from telemetry already collected on Edge1. It does not alter Suricata, Unbound, nftables, Fail2ban, Spamhaus filtering, proxy services, or network policy.

## Inputs

- `/var/www/edge1-status/security-operations.json`
- `/var/www/edge1-status/operations-network.json`
- `/var/lib/bigbird/operations-center/latest.json`
- `/var/lib/bigbird-networking/spamhaus/summary.txt`

Missing or malformed optional inputs are reported as warnings while the remaining sources continue to export.

## Output

Authoritative service output:

- `/var/www/edge1-status/security/correlation/data/security-correlation.json`

Compatibility read path:

- `/var/www/edge1-status/security-correlation.json`

The compatibility path is an installer-managed symbolic link to the scoped data file. The service can write only inside the root-owned `security/correlation/data` directory and retains an empty capability set.

The output includes source availability, privacy declarations, normalized events, correlation chains, limitations, and aggregate counts. Packet payloads, credentials, private keys, and unrestricted raw logs are not included.

## Correlation model

An IDS alert becomes a correlation anchor. DNS, firewall, and Fail2ban events are related when their timestamps fall within the configured correlation window and an endpoint or domain overlaps.

One matching category produces medium confidence. Two or more distinct related categories produce high confidence. Correlation is an investigative lead, not proof of causation.

## Runtime

- `wwcx-security-correlation.service`
- `wwcx-security-correlation.timer`

The service is a hardened one-shot exporter. The timer refreshes the snapshot every minute. The browser console is at `src/web/security/correlation.html`.

## Deployment

Use the bounded installer from `main`:

```bash
sudo bash ./deploy/install-security-correlation-observability.sh
```

The installer validates the repository, backs up affected paths, creates the scoped data directory, installs the service and timer, verifies the privacy contract and local HTTP endpoint, and restores the prior state automatically if a live check fails.

## Validation

```bash
bash tools/security/validate-security-correlation.sh
```

## Safety boundary

- no shell command execution by the exporter;
- no packet capture or packet payload storage;
- no firewall, DNS, IDS, proxy, reputation-filter, or Fail2ban mutation;
- no server-side action endpoint;
- browser evidence export is local-only;
- runtime write access is limited to the scoped correlation data directory.
