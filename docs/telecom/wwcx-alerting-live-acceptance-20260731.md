# WW.CX Alerting Laboratory Live Acceptance

**Execution date:** 2026-07-31 UTC  
**Host:** `edge1.ww.cx`  
**Operator principal:** `wwadmin` with bounded `sudo` elevation  
**Repository:** `johnkaminski727-alt/edge1-management-interface`  
**Minimum confirmed repository state:** contains continuity merge `03d219e853bd8a373cd9d0503c45579901615017`

## Accepted live changes

The guarded Asterisk 22 package update completed and validated successfully.

- running Asterisk version: `22.10.1`;
- previous directly observed version: `22.8.2`;
- Asterisk restarted successfully;
- zero active channels and zero active calls were observed after restart;
- Kamailio remained active;
- `app_playtones`, `app_senddtmf`, DSP, `chan_pjsip`, `res_pjsip`, and `res_pjsip_sdp_rtp` were running;
- no PJSIP endpoints were configured;
- no alerting-related dialplan match was present.

The offline alerting laboratory was installed under:

```text
/opt/wwcx-alerting-lab
```

Installed assets are root-owned and include the CAP-CP structural probe, lifecycle/replay probe, legacy EBS receive-side tone detector, Asterisk readiness audit, synthetic bilingual test fixture, and deny-by-default laboratory policy.

## Validation results

The installed synthetic CAP-CP test alert passed structural validation with:

- CAP-CP profile `1.0`;
- `Test` status;
- `Restricted` scope;
- bilingual `en-CA` and `fr-CA` information blocks;
- one `testMessage` subject event type;
- two targeted areas;
- no errors or warnings.

The lifecycle probe accepted the same synthetic message as one active test alert with no duplicate, replay, reference, freshness, or lifecycle error.

No CAP source, network listener, Asterisk dialplan, endpoint, call route, page group, tone generator, SIP/PSTN delivery path, or public alert distribution capability was activated.

## Protected evidence

```text
/var/lib/wwcx-deployment-evidence/asterisk-security-update/20260731T233728Z
/var/lib/wwcx-deployment-evidence/alerting-lab-install/20260731T233821Z
```

Operator-local rollout evidence:

```text
/home/wwadmin/edge1-alerting-rollout-20260731T233717Z
```

The earlier interrupted update evidence remains retained:

```text
/var/lib/wwcx-deployment-evidence/asterisk-security-update/20260731T231305Z
```

## Residual warnings

### PJSIP transport reporting discrepancy

`pjsip show transports` returned `No objects found`, but the Asterisk process was directly observed owning UDP `127.0.0.1:5061`. This is not accepted as a configured transport conclusion until configuration and runtime object loading are reconciled.

### Boot persistence not confirmed

The generated legacy SysV-backed systemd wrapper reported active, while `systemctl is-enabled asterisk` reported disabled. The running process is healthy, but restart-after-reboot behavior must be verified from SysV startup links and the generated unit before changing enablement.

### TCP 8089 exposure

Asterisk TCP `8089` was listening on a non-loopback wildcard address. TLS, certificate identity, authentication, firewall reachability, and operational need require read-only verification before any listener change.

## Follow-up audit

Run the merged read-only audit after updating the Edge1 checkout:

```sh
cd /opt/edge1-management-interface
git pull --ff-only origin main
sudo sh tools/alerting/asterisk_warning_followup_audit.sh \
  --expected-host edge1.ww.cx
```

The audit does not modify packages, services, startup policy, Asterisk configuration, listeners, routes, certificates, or firewall rules.

## Acceptance boundary

Accepted:

- Asterisk `22.10.1` package update and restart;
- offline CAP-CP/EBS laboratory installation;
- synthetic structural and lifecycle validation;
- preserved protected evidence;
- base Asterisk media and signaling capability.

Not accepted or authorized:

- an operational CAP-CP feed;
- `Actual` alert ingestion;
- alert origination or redistribution;
- Asterisk call or page delivery;
- EBS/EAS attention-tone transmission;
- public Alert Ready, NPAS, EAS, EBS, or regulatory certification claims;
- listener, firewall, routing, certificate, or boot-policy changes.
