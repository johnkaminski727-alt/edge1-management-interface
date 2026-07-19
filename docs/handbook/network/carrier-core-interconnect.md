# Carrier Core and Interconnect Standard

## Purpose

This standard defines the target control boundaries for WW.CX carrier-facing voice infrastructure. It is an engineering baseline and does not assert production carrier status, numbering authority, regulatory approval, or completed interconnection.

## Architecture principles

- Public SIP ingress MUST terminate on a dedicated session border function before reaching PBX or application systems.
- Signalling, media, management, monitoring, and customer-provisioning planes MUST be logically separated.
- Production, staging, laboratory, and documentation-only environments MUST use distinct credentials, endpoints, and evidence records.
- Carrier routes MUST have an identified owner, change record, rollback method, health check, and customer-impact assessment.
- Direct public exposure of FreePBX, Asterisk administration, databases, message queues, or management APIs is prohibited.

## Reference flow

```text
Carrier / CLEC / Messaging Provider
              |
        Public SIP or API
              |
      Edge firewall and ACLs
              |
       SBC / SIP edge tier
        |              |
   Routing proxy     Media relay
        |              |
      PBX / service applications
              |
 Provisioning, records, monitoring, evidence
```

## Interconnect inventory

Every interconnect MUST record:

- provider and service name;
- commercial and technical contacts;
- signalling addresses and transport;
- authentication model;
- codec and DTMF policy;
- emergency calling treatment;
- numbering and portability dependencies;
- STIR/SHAKEN expectations;
- maintenance windows;
- test cases and last verified date;
- rollback and isolation procedure.

Secrets, private keys, bearer tokens, and full credentials MUST NOT be stored in the handbook or Git history.

## Routing and failover

Routing policy MUST be deterministic, reviewable, and testable. Failover routes MUST not silently bypass emergency-calling, fraud-control, lawful-authority, identity, or customer-policy controls. Route changes MUST include pre-change and post-change call tests, observable metrics, and an expiry for temporary exceptions.

## Readiness gates

An interconnect is not production-ready until signalling, media, inbound, outbound, caller identity, failure handling, emergency treatment, monitoring, support escalation, and evidence capture have all been validated in an approved environment.
