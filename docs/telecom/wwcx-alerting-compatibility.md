# WW.CX EBS and CAP-CP Compatibility Foundation

**Status:** repository-staged, receive-side and test-only  
**Production alert origination:** prohibited  
**Public distribution:** not implemented  
**Last reviewed:** 2026-07-31

## Objective

Provide a bounded compatibility foundation for receiving and validating OASIS CAP 1.2 messages that identify the Canadian CAP-CP 1.0 profile, tracking Alert/Update/Cancel lifecycle state, and recognizing the retired U.S. Emergency Broadcast System 853/960 Hz attention signal in recorded PCM audio.

Compatibility is not certification. This foundation does not make WW.CX, CreekCo, Asterisk, or Edge1 an authorized Alert Ready, NPAS, EAS, EBS, or emergency-alert origination system.

## Normative baseline

The implementation is aligned to these public specifications and guidance:

- OASIS Common Alerting Protocol 1.2;
- Public Safety Canada CAP-CP 1.0 Introduction and Rule Set;
- independently versioned CAP-CP Event References and Location References;
- NPAS Common Look and Feel guidance as a future last-mile presentation requirement, not as an implemented feature.

CAP-CP requires valid CAP, one subject event type per message, an identified CAP-CP profile version, languages on information blocks, recognized event references, and location identification through CAP geometry and/or CAP-CP location references. Operational communities may impose additional delivery and presentation requirements.

## Implemented components

### Structural CAP-CP probe

`tools/alerting/capcp_probe.py` validates a bounded local XML file, blocks DTD/entity declarations, requires the CAP 1.2 namespace and CAP-CP markers, checks required fields, multilingual event consistency and location targeting, rejects `Actual` alerts by default, and emits sanitized JSON. It performs no network access and has no transmission path.

### Lifecycle and replay probe

`tools/alerting/capcp_lifecycle_probe.py` evaluates an ordered set of local CAP-CP files and adds:

- duplicate message-key detection;
- optional freshness and future-clock-skew checks;
- required references for `Update` and `Cancel` messages;
- same-sender reference enforcement;
- active, superseded, cancelled, and terminal-cancel state tracking;
- sanitized SHA-256-backed processing records.

It stores no persistent state and cannot fetch or distribute an alert.

### Legacy EBS receive-side probe

`tools/alerting/ebs_tone_probe.py` accepts a bounded uncompressed 16-bit PCM WAV file and detects simultaneous energy near 853 Hz and 960 Hz. It never generates, plays, routes, or transmits an attention signal.

### Asterisk readiness audit

`tools/alerting/asterisk_alerting_readiness.sh` performs a read-only host audit of the Asterisk process, version, channel count, required media and DTMF modules, PJSIP transport posture, endpoints, service wrapper, listeners, and any existing alert-related dialplan matches.

The audit reports base capability only. It does not add a dialplan, endpoint, call route, page group, feed, listener, or transmission path.

### Offline laboratory installer

`deploy/alerting/install-alerting-lab.sh` validates and stages the probes under `/opt/wwcx-alerting-lab`. It defaults to dry-run and requires `--apply`. Even when applied it creates no service, network socket, CAP feed, Asterisk configuration, Kamailio configuration, firewall rule, or call route.

The installed policy is `config/alerting/wwcx-alerting-lab-policy.json`. It explicitly denies Actual alerts, Public scope, networking, tone generation, SIP/PSTN delivery, call origination, and Asterisk dialplan changes.

### Guarded Asterisk updater

`deploy/telephony/asterisk22-guarded-update.sh` replaces the interrupted inline update command. It fixes the earlier `pipefail` candidate-detection failure, defaults to a simulation, refuses active calls, refuses package removal or a non-22 candidate, preserves configuration, requires `--apply`, restarts through FreePBX when available, and captures protected evidence.

The script is staged only. Repository presence is not evidence that the live Asterisk package was updated.

## Safe architecture

```text
Authorized CAP-CP source (not configured)
        |
        v
Quarantined local ingress (not implemented)
        |
        v
CAP 1.2 + CAP-CP validation
        |
        v
Lifecycle, replay, freshness and trust checks
        |
        v
Normalized internal alert record
        |
        v
Human/policy approval gate
        |
        +--> read-only display
        +--> isolated audio-rendering test
        +--> future Asterisk adapter, disabled until separately authorized
```

Asterisk must remain a delivery adapter, not the trust authority. It must never accept arbitrary public XML and immediately originate calls or pages.

## Required gates before live delivery

- written authority to consume the selected CAP-CP feed;
- documented endpoint, trust anchors, authentication and redistribution terms;
- complete normative CAP 1.2 schema and CAP-CP rule-set validation;
- managed event/location reference validation;
- signature and issuer trust policy where required;
- persistent replay, duplicate, update, cancel, expiry and clock-skew controls;
- bilingual rendering and accessibility review;
- geographic targeting and Test/Exercise/Actual separation;
- protected activation control with dual authorization where appropriate;
- audit, retention, rollback and incident procedures;
- formal conformance and governance review before any public claim.

## Repository validation

```bash
python3 -m py_compile \
  tools/alerting/capcp_probe.py \
  tools/alerting/capcp_lifecycle_probe.py \
  tools/alerting/ebs_tone_probe.py \
  tests/test_alerting_compatibility.py
python3 -m unittest -v tests/test_alerting_compatibility.py
bash -n tools/alerting/asterisk_alerting_readiness.sh
bash -n deploy/alerting/install-alerting-lab.sh
bash -n deploy/telephony/asterisk22-guarded-update.sh
python3 -m json.tool config/alerting/wwcx-alerting-lab-policy.json >/dev/null
```

The targeted suite contains nine tests covering structural validation, Actual-alert blocking, one-event enforcement, duplicate suppression, Update/Cancel lifecycle, missing references, freshness limits, EBS dual-tone recognition, and single-tone rejection.

## Edge1 operator sequence

Run only from a clean checkout of the reviewed branch or merged revision:

```bash
cd /opt/edge1-management-interface
git status --short --branch

# Read-only Asterisk capability audit
sudo bash tools/alerting/asterisk_alerting_readiness.sh \
  --expected-host edge1.ww.cx

# Read-only package simulation
sudo bash deploy/telephony/asterisk22-guarded-update.sh \
  --expected-host edge1.ww.cx

# Offline laboratory installation dry-run
sudo bash deploy/alerting/install-alerting-lab.sh \
  --expected-host edge1.ww.cx
```

Do not use either `--apply` option until the branch revision, simulation output, active-call state, and rollback evidence path have been reviewed. Applying the laboratory installer is bounded and does not activate alerts. Applying the Asterisk updater restarts the PBX and is a maintenance operation.

## Asterisk boundary

The measured Edge1 Asterisk instance has the audio and dialplan primitives needed for a future controlled adapter, but no CAP-CP alert context, authorized endpoint, protected activation workflow or public-delivery authority exists. Do not add an inbound public route, automatic call origination, paging group, carrier path, tone generator, or live CAP feed as part of this foundation.
