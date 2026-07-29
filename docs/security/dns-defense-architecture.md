# WW.CX DNS Defense architecture

## Decision

Retain Unbound as the recursive DNS core and introduce repository-managed Response Policy Zone (RPZ) assets in observation-only staging before considering enforcement.

This phase does not modify the active resolver, install includes, change `module-config`, reload Unbound, or alter DNS answers.

## Staged topology

```text
Clients
  |
  v
Existing Unbound recursive resolver
  |
  +-- future explicitly installed RPZ include
        |
        +-- staged policy zone
            action override: disabled
            logging: enabled
```

The generated include uses `rpz-action-override: disabled`. Activation requires the Unbound `respip` module and a separate authenticated change process.

## Repository components

- `config/dns-defense/policy.example.json` — reserved example domains only;
- `tools/networking/compile-dns-defense-policy.py` — deterministic compiler;
- `tools/networking/validate-dns-defense-policy.sh` — aggregate validation;
- `tests/test_dns_defense_policy.py` — safety tests;
- `tests/validate_dns_defense_policy.py` — CI entrypoint.

## Policy contract

Each entry contains:

- `domain` — normalized and validated;
- `action` — `nxdomain`, `nodata`, or `passthru`;
- `include_subdomains` — optionally emits wildcard triggers;
- `reason` — human-readable rationale.

Rejected:

- duplicate domains;
- embedded wildcards;
- single-label names;
- malformed domains;
- unsupported actions;
- unsafe TTL values;
- oversized policies.

## Safety boundary

The compiler only creates staged files. It:

- does not install Unbound configuration;
- does not reload DNS services;
- does not make network requests;
- does not read credentials;
- emits `enforcement_enabled: false` and `traffic_controls_changed: false`.

## Activation gates

Before any live use:

1. inspect active Unbound configuration and module support;
2. validate generated assets with installed resolver tooling;
3. deploy shadow/disabled mode first;
4. verify DNSSEC, latency, logging, and rollback;
5. obtain explicit authorization before enabling enforcement.
