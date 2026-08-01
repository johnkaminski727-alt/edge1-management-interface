# WW.CX Outbound Mail Gateway — Phase A Disabled Deployment

## Objective

Install the merged outbound-mail gateway on Edge1 as a loopback-only, disabled foundation. This phase starts the local administrative and preview service but must not enable the authenticated preparation API, public routing, provider submission, or live delivery.

## Port 8094 conflict and resolution

The initial gateway configuration used port 8094. Edge1 already reserves `127.0.0.1:8094` for `edge1-electrum-watch-api.service`. The outbound-mail service therefore uses `127.0.0.1:8104`.

The installer refuses to proceed when port 8104 is occupied by another listener. It never stops or replaces an unknown process to obtain the port.

## Authorization boundary

This runbook covers Phase A only:

- update the Edge1 repository to an approved `main` commit;
- run repository validation;
- install or update `wwcx-outbound-mail-gateway.service`;
- bind only to `127.0.0.1:8104`;
- verify disabled preparation and delivery gates;
- capture evidence and preserve rollback.

It does not authorize secrets, authentication changes, a reverse proxy, DNS, firewall or certificate work, public correspondence-record activation, retention apply, provider credentials, or production mail traffic.

## Required execution path

Run these commands through an authenticated Edge1 shell as an authorized operator. Do not paste credentials or secret values into the repository, command line, issue, or evidence directory.

## 1. Preflight and protect existing work

```sh
cd /opt/edge1-management-interface

hostname -f
id
git branch --show-current
git status --short --branch
git remote -v
systemctl status edge1-electrum-watch-api.service --no-pager -l || true
sudo ss -lntp | grep -E ':(8094|8104)\b' || true
```

Stop when:

- the host is not the expected Edge1 host;
- the repository is not on `main`;
- tracked working-tree changes exist;
- port 8104 is occupied by an unknown listener;
- the Electrum API is not still associated with port 8094;
- the approved commit cannot be identified.

Do not reset, clean, stash, or overwrite unrelated work merely to continue.

## 2. Update to the approved main commit

```sh
cd /opt/edge1-management-interface
git fetch --prune origin main
git pull --ff-only origin main
APPROVED_COMMIT=$(git rev-parse HEAD)
printf 'approved_commit=%s\n' "$APPROVED_COMMIT"
git status --short --branch
```

Compare `APPROVED_COMMIT` with the merge commit recorded in activation issue #187 before installing.

## 3. Run the complete repository validation suite

```sh
cd /opt/edge1-management-interface
set -eu
for validator in tests/validate_*.py; do
  printf '=== %s ===\n' "$validator"
  python3 "$validator"
done
python3 -m compileall -q bin server tests tools
find bin deploy tools -type f -name '*.sh' -print0 |
  while IFS= read -r -d '' script; do
    sh -n "$script"
  done
```

The outbound-mail deployment validator must report that Electrum remains on 8094 and the outbound gateway uses loopback 8104.

## 4. Install the disabled service

```sh
cd /opt/edge1-management-interface
sudo EXPECTED_COMMIT="$APPROVED_COMMIT" \
  sh deploy/messaging/install-outbound-mail-gateway.sh
```

The installer performs these controls before and during mutation:

- refuses a non-`main` branch;
- refuses tracked working-tree changes;
- optionally requires an exact `EXPECTED_COMMIT`;
- verifies every gateway, policy, provider, preparation API, and sender activation flag remains disabled;
- refuses an occupied port 8104 unless the existing gateway service is already active;
- creates a dedicated non-login service account;
- preserves the previous unit and enabled/active state;
- installs the hardened loopback service;
- runs the no-send smoke test;
- automatically restores the previous unit and service state when validation fails;
- writes a timestamped evidence bundle under `/var/lib/wwcx-deployment-evidence/outbound-mail-phase-a/`.

## 5. Independent post-install verification

```sh
sudo systemctl status wwcx-outbound-mail-gateway.service --no-pager -l
sudo systemctl show wwcx-outbound-mail-gateway.service \
  -p ActiveState -p SubState -p UnitFileState -p User -p Group \
  -p ExecStart -p FragmentPath -p MainPID
sudo ss -lntp | grep -E ':(8094|8104)\b'

curl -fsS http://127.0.0.1:8104/outbound-mail/healthz
curl -fsS http://127.0.0.1:8104/outbound-mail/status | python3 -m json.tool
HOST=127.0.0.1 PORT=8104 \
  sh deploy/messaging/outbound-mail-gateway-smoke-test.sh
```

Required results:

- the service is active and enabled;
- the service runs as `wwcx-mail-gateway`;
- 8104 is bound only to loopback;
- 8094 remains the Electrum API port;
- gateway state is `disabled`;
- preparation API is disabled and unauthenticated access returns HTTP 403;
- every sender remains live-disabled;
- every provider remains unavailable for delivery;
- a send probe is rejected with `delivery_disabled`;
- no external preparation request and no external delivery can succeed.

## 6. Evidence review

The installer prints the evidence directory. Review at minimum:

```sh
sudo find /var/lib/wwcx-deployment-evidence/outbound-mail-phase-a \
  -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort | tail

EVIDENCE_DIR=/var/lib/wwcx-deployment-evidence/outbound-mail-phase-a/<TIMESTAMP>
sudo cat "$EVIDENCE_DIR/preflight.txt"
sudo cat "$EVIDENCE_DIR/service-properties.txt"
sudo cat "$EVIDENCE_DIR/smoke-test.txt"
sudo cat "$EVIDENCE_DIR/status.json" | python3 -m json.tool
sudo sha256sum -c "$EVIDENCE_DIR/SHA256SUMS"
```

Do not publish unredacted journals or host data externally. The bundle contains no intentionally stored credential values, but it must still be treated as operational evidence.

## Rollback

The installer automatically rolls back the service unit and enabled/active state when its own validation fails. For a later operator-initiated rollback, use the preserved unit in the relevant evidence directory:

```sh
sudo systemctl stop wwcx-outbound-mail-gateway.service

if [ -f "$EVIDENCE_DIR/previous-unit.service" ]; then
  sudo install -m 0644 "$EVIDENCE_DIR/previous-unit.service" \
    /etc/systemd/system/wwcx-outbound-mail-gateway.service
else
  sudo rm -f /etc/systemd/system/wwcx-outbound-mail-gateway.service
fi

sudo systemctl daemon-reload
sudo systemctl disable wwcx-outbound-mail-gateway.service || true
sudo systemctl status wwcx-outbound-mail-gateway.service --no-pager -l || true
sudo ss -lntp | grep ':8104\b' || true
```

Do not delete the service account, runtime directory, or evidence bundle during emergency rollback. Retention or removal can be reviewed separately after the previous state is confirmed.

## Deferred phases

Separate explicit authorization remains required before:

- installing an HMAC secret;
- enabling `preparation_api.enabled`;
- exposing an authenticated reverse proxy;
- enabling the WW.CX website bridge;
- activating the public correspondence record;
- applying or scheduling telemetry retention;
- installing provider credentials;
- changing SPF, DKIM, DMARC, DNS, firewall, or certificates;
- sending any production message.
