# BigBird Messaging Adapter

This integration lets BigBird manage the WW.CX messaging gateway through its internal management API. BigBird never receives database or carrier credentials and never calls provider adapters directly.

## Tool mapping

| BigBird tool | Required scope | Gateway operation |
|---|---|---|
| `messaging.status.read` | `messaging.status.read` | `GET /v1/management/status` |
| `messaging.control.pause` | `messaging.control.pause` | `POST /v1/management/control` with `action=pause` |
| `messaging.control.resume` | `messaging.control.resume` | `POST /v1/management/control` with `action=resume` |

## Runtime configuration

Configure these through the BigBird service secret environment, never in source control:

- `WWCX_MESSAGING_MANAGEMENT_URL`
- `WWCX_MESSAGING_READ_TOKEN`
- `WWCX_MESSAGING_CONTROL_TOKEN`

The read and control credentials must remain separate. Omit the control token to make the adapter read-only.

## Registry integration

1. Load `tool-manifest.json` into the BigBird tool registry.
2. Bind each tool to the matching authorization scope.
3. Construct `MessagingGatewayClient` from the service environment.
4. Derive `actor` from the authenticated BigBird principal, not model-generated text.
5. Require a non-empty operator reason for pause and resume.
6. Record the BigBird request audit event before invoking a mutating tool.
7. Keep the messaging gateway's own audit record as the authoritative downstream action record.

## Safety defaults

- The manifest is disabled by default.
- Status uses only the read credential.
- Pause and resume require the separate control credential.
- The messaging gateway must also have `WWCX_MANAGEMENT_CONTROL_ENABLED=true` before it accepts control operations.
- The adapter does not expose message bodies, recipient lists, provider credentials, database access, carrier provisioning, or outbound submission.

## Validation

```sh
python -m unittest discover -s integrations/bigbird-messaging/tests -v
python -m compileall -q integrations/bigbird_messaging
python -m json.tool integrations/bigbird-messaging/tool-manifest.json >/dev/null
```

## Deployment boundary

This repository publishes the tested adapter and registry contract. Installing it into `/opt/bigbird-ai-gateway`, setting service secrets, enabling scopes, or restarting the live BigBird service are separate production changes and require an Edge1 deployment review.
