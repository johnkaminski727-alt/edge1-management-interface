# WW.CX Numbering Dataset Operations

This runbook covers the local, loopback-only WW.CX numbering intelligence node on Edge1. It does not authorize or activate public SIP, carrier routing, number assignment, portability, emergency calling, DNS, firewall, certificate, FreePBX, or Asterisk changes.

## Scope and safety

- Service: `wwcx-numbering-node.service`
- Database: `/var/lib/wwcx-numbering-node/numbering.sqlite3`
- HTTP listener: `127.0.0.1:8093`
- Application: `server/wwcx_numbering_node.py`
- Dataset imports are offline operator actions.
- Every source name must be stable, descriptive, and non-secret.
- Synthetic data must remain clearly labelled and must not be represented as official carrier, CNAC, NANPA, CRTC, LERG, or portability data.
- Verify source licensing and redistribution terms before importing any official dataset.

## Preflight

```bash
cd /opt/edge1-management-interface

git status --short
sh deploy/interconnect/validate-staging-assets.sh
python3 -m unittest discover -s tests -p 'test_wwcx_numbering_node.py' -v
sudo systemctl is-active wwcx-numbering-node.service
curl -fsS http://127.0.0.1:8093/healthz
```

Stop if the repository has unrelated changes, validation fails, the service is unhealthy, or the listener is not restricted to loopback.

## Inspect current sources

```bash
sudo -u wwadmin python3 server/wwcx_numbering_node.py \
  --database /var/lib/wwcx-numbering-node/numbering.sqlite3 \
  list-sources | python3 -m json.tool
```

Record the current source list and health output in the change evidence.

## Prepare an import

Required logical fields are NPA and NXX. Accepted aliases are handled by the importer, but operators should prefer this canonical header:

```text
npa,nxx,country,region,rate center,ocn,company,status,source updated
```

Before import:

```bash
SOURCE='descriptive-source-name'
CSV='/path/to/source.csv'

sha256sum "$CSV"
head -n 3 "$CSV"
wc -l "$CSV"
```

Do not place credentials, private customer records, message content, or unlicensed proprietary datasets in the CSV.

## Atomic source replacement

Use source replacement for repeatable refreshes. The importer validates rows before replacing the existing source, preventing a partial source refresh from becoming active.

```bash
sudo -u wwadmin python3 server/wwcx_numbering_node.py \
  --database /var/lib/wwcx-numbering-node/numbering.sqlite3 \
  import-csv \
  --source "$SOURCE" \
  --replace-source \
  "$CSV"
```

Capture the JSON result. It should report the source, accepted rows, rejected rows, SHA-256 value, and import time.

## Post-import verification

```bash
sudo -u wwadmin python3 server/wwcx_numbering_node.py \
  --database /var/lib/wwcx-numbering-node/numbering.sqlite3 \
  list-sources | python3 -m json.tool

curl -fsS http://127.0.0.1:8093/healthz | python3 -m json.tool

sudo ss -lntp | grep -E '127\.0\.0\.1:8093([[:space:]]|$)'
```

Perform at least one known-positive lookup and one known-negative lookup. A negative lookup should return HTTP 404.

```bash
curl -fsS 'http://127.0.0.1:8093/v1/lookup?number=14165551212' | python3 -m json.tool
curl -sS -o /tmp/wwcx-negative-lookup.json -w '%{http_code}\n' \
  'http://127.0.0.1:8093/v1/lookup?number=12125550100'
cat /tmp/wwcx-negative-lookup.json
```

Use numbers appropriate to the imported source. Do not treat the examples above as official assignments.

## Controlled source removal

Removal is appropriate for synthetic fixtures, withdrawn datasets, or an operator-approved rollback.

```bash
SOURCE='wwcx-controlled-test'

sudo -u wwadmin python3 server/wwcx_numbering_node.py \
  --database /var/lib/wwcx-numbering-node/numbering.sqlite3 \
  remove-source \
  --source "$SOURCE"
```

Immediately verify `list-sources`, `/healthz`, and a lookup formerly supplied by that source.

## Rollback

Preferred rollback is an atomic replacement using the previously verified CSV file and checksum.

```bash
PREVIOUS_CSV='/path/to/previous-verified-source.csv'
SOURCE='descriptive-source-name'

sha256sum "$PREVIOUS_CSV"

sudo -u wwadmin python3 server/wwcx_numbering_node.py \
  --database /var/lib/wwcx-numbering-node/numbering.sqlite3 \
  import-csv \
  --source "$SOURCE" \
  --replace-source \
  "$PREVIOUS_CSV"
```

If the service becomes unhealthy, stop further changes and collect:

```bash
sudo systemctl status wwcx-numbering-node.service --no-pager -l
sudo journalctl -u wwcx-numbering-node.service -n 100 --no-pager
sudo ss -lntp | grep -E ':(8093)([[:space:]]|$)' || true
```

Do not delete or replace the SQLite database directly during routine rollback. Direct database restoration requires a separately reviewed backup and recovery procedure.

## Evidence checklist

Record:

- operator and timestamp;
- repository branch and commit;
- source name and source authority;
- licensing or redistribution verification status;
- input file name, row count, and SHA-256;
- importer JSON result;
- source listing before and after;
- health output before and after;
- positive and negative lookup results;
- loopback listener confirmation;
- rollback file and checksum;
- unresolved rejected rows or data-quality concerns.

## Approval boundaries

Pause before:

- importing an official dataset whose usage terms have not been verified;
- representing imported records as legal numbering assignments or routing authority;
- connecting the data to live routing, billing, portability, STIR/SHAKEN, emergency calling, or customer-facing decisions;
- changing the listener away from `127.0.0.1`;
- changing firewall, DNS, certificates, Asterisk, FreePBX, or Kamailio production state.
