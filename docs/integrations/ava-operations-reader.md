# Ava Operations Reader

The Ava Operations Reader is a fail-closed, read-only profile over the existing
BigBird–Edge1 control-plane broker. It does not duplicate SSH or operator
credentials and it does not expose arbitrary shell, paths, URLs, services,
commands, SQL, environment values, or action names.

## Initial capability set

The profile exposes bounded status, services, addresses, routes, disk, Apache,
Asterisk, Big Bird health/tool registry, repository status/head, and approved
configuration digests. The Operations API health response is included in
capability discovery.

Every call returns:

- the profile, capability, scope, and read-only classification;
- an observation timestamp and maximum accepted age;
- the Operations API audit event ID and bounded execution metadata;
- JSON-decoded output when the broker returns JSON, otherwise bounded text;
- only the presence of stderr, never credential or environment values.

## Safety boundary

The profile refuses staged writes, apply, reload, deployment, repository fetch,
branch writes, service control, and every capability not explicitly listed.
The adapter checks the profile, BigBird capability manifest, and tool manifest
on every call and fails closed on missing capabilities, class drift, scope drift,
enablement drift, or unexpected input schema.

Draft preparation capabilities are outside this profile. Their non-sending
artifact semantics should be represented separately from strict read-only
operations.

## Validation

```text
python3 -m unittest tests.test_ava_operations_reader -v
python3 -m unittest tests.validate_bigbird_edge1_control_plane_v2 -v
python3 -m unittest tests.validate_bigbird_control_plane_tool_manifest_v2 -v
```

## Deployment boundary

This change is repository-only until separately approved. Deployment should:

1. install the profile and tool manifest from a reviewed commit;
2. run capability discovery and require every selected capability available;
3. expose the adapter to Ava with only the scopes in the tool manifest;
4. smoke-test capability discovery and one harmless bounded read;
5. verify Operations API mutations remain disabled;
6. preserve the previous Ava registry and service configuration for rollback.

Rollback consists of restoring the previous Ava tool registry/service revision.
No firewall, DNS, proxy, VPN, telephony, or production traffic change belongs
to this deployment.
