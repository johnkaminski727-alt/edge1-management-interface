# Edge1 Security Completion Programs Runbook

Date: 2026-07-30  
Repository: `johnkaminski727-alt/edge1-management-interface`  
Scope: protected Suricata retention, minimized public summary, authenticated detailed operations, staged public cutover

## Safety model

The runtime consumes only the already-sanitized `wwcx.suricata-source-alert.v1` snapshot. It does not read raw EVE, modify Suricata, alter DNS, Unbound, RPZ, nftables, firewall rules, routing, reputation lists, IDS rules, certificates, public listeners, or production traffic. Retention rollback preserves the SQLite database. Public cutover archives the detailed tree and changes URL routing; it does not delete detailed operational files.

## Credential boundary

No credential material is stored in Git. Deployment requires:

- `EDGE1_AUTH_USER_FILE`: an existing approved root-owned Apache password file, mode `0640` or stricter;
- `EDGE1_AUTH_ACCEPTANCE_FILE`: a temporary root-owned mode-`0600` JSON file containing only `username` and `password` strings for automated acceptance.

The scripts never copy these values into evidence and remove the temporary cookie jar. Do not provide these values in chat.

## Execution

From a clean, fast-forwarded `main` checkout on `edge1.ww.cx`:

```bash
cd /opt/edge1-management-interface
git pull --ff-only origin main
git status --short --branch

sudo EDGE1_AUTH_USER_FILE=/absolute/path/to/approved.htpasswd \
  EDGE1_AUTH_ACCEPTANCE_FILE=/root/protected/edge1-acceptance.env \
  bash deploy/activate-edge1-security-completion-programs.sh
```

The orchestrator runs the read-only completion preflight, retention deployment, authenticated parallel stage, and public cutover in that order.

## Acceptance gates

Cutover is impossible unless all of the following pass:

1. repository `main` is clean and validation passes;
2. required Apache form/session, header, audit-environment, alias, and rate-limit modules are enabled;
3. the approved authentication and acceptance files are root-owned and tightly permissioned;
4. minimized status generation succeeds with the exact seven-field allowlist;
5. anonymous `/edge1-ops/` fails closed;
6. an authenticated browser-equivalent form login reaches the detailed root and selected detailed JSON routes;
7. detailed access is audited and response-rate-limited;
8. the detailed public tree is inventoried, hashed, and archived under protected evidence;
9. Apache config test and reload succeed;
10. minimized public routes return the required headers and exact schema;
11. superseded anonymous detailed routes return `404`;
12. authenticated detailed routes still return `200`;
13. listener state remains unchanged.

Any failure after mutation restores the preceding Apache stage or prior installed assets. Operational data and archives are preserved.

## Units and installed files

- `wwcx-suricata-protected-retention.service` and `.timer`;
- `wwcx-edge1-minimized-public-summary.service` and `.timer`;
- `/usr/local/libexec/wwcx-security/suricata_protected_retention.py`;
- `/usr/local/libexec/wwcx-security/edge1_public_status_exporter.py`;
- `/etc/wwcx/security/suricata-protected-retention-runtime.json`;
- `/etc/apache2/conf-available/edge1-security-boundary.conf`;
- `/var/lib/bigbird-security/suricata-history/` (root-only);
- `/var/lib/bigbird-public-status/www/` (minimized public tree);
- `/var/www/edge1-status/` (preserved detailed tree, authenticated at `/edge1-ops/`).

## Evidence roots

```text
/var/lib/wwcx-deployment-evidence/edge1-security-completion-preflight/<UTC timestamp>
/var/lib/wwcx-deployment-evidence/suricata-protected-retention/<UTC timestamp>
/var/lib/wwcx-deployment-evidence/edge1-public-boundary-stage/<UTC timestamp>
/var/lib/wwcx-deployment-evidence/edge1-public-boundary-cutover/<UTC timestamp>
```

Each deployment directory is root-only and includes a SHA-256 manifest. The cutover evidence contains the protected archive of the former detailed public tree.
