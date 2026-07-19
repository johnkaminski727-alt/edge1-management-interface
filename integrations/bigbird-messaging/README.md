# BigBird Messaging Adapter

This integration lets BigBird manage the WW.CX messaging gateway through a versioned internal management API. BigBird never receives database or carrier credentials and never calls provider adapters directly.

## Recommended architecture

1. The messaging gateway owns message state, provider adapters, control state, and its downstream audit log.
2. The versioned `management-api-v1.json` contract is the boundary between services.
3. `integrations.bigbird_messaging.MessagingGatewayClient` performs internal HTTP calls.
4. `BigBirdMessagingTools` validates runtime configuration and fails closed.
5. `tool-manifest.json` maps each operation to an explicit BigBird authorization scope.
6. BigBird records the authenticated principal and request audit before a control call.
7. Edge1 deployment stages files before any live registry or service change.

## Tool mapping

| BigBird tool | Required scope | Gateway operation |
|---|---|---|
| `messaging.status.read` | `messaging.status.read` | `GET /v1/management/status` |
| `messaging.control.pause` | `messaging.control.pause` | `POST /v1/management/control` with `action=pause` |
| `messaging.control.resume` | `messaging.control.resume` | `POST /v1/management/control` with `action=resume` |

## Runtime configuration

Configure these through the BigBird service secret environment, never in source control:

- `WWCX_MESSAGING_BASE_URL`
- `WWCX_MESSAGING_READ_TOKEN`
- `WWCX_MESSAGING_CONTROL_ENABLED`
- `WWCX_MESSAGING_CONTROL_TOKEN`

The read and control credentials must remain separate. Control defaults to disabled and enabling it without a configured control token fails startup validation.

## Registry integration

1. Load `tool-manifest.json` into the BigBird tool registry.
2. Bind each tool to the matching authorization scope.
3. Construct `MessagingToolConfig` from the service environment.
4. Derive `actor` from the authenticated BigBird principal, never model-generated text.
5. Require a non-empty operator reason for pause and resume.
6. Record the BigBird request audit event before invoking a mutating tool.
7. Keep the messaging gateway audit record as the authoritative downstream action record.
8. Do not expose generic HTTP, arbitrary actions, message content, or provider operations through this adapter.

## Safety defaults

- The registry manifest is disabled by default.
- Status uses only the read credential.
- Pause and resume require a separate control credential and enable flag.
- The messaging gateway independently requires `WWCX_MANAGEMENT_CONTROL_ENABLED=true`.
- The adapter does not expose message bodies, recipient lists, provider credentials, database access, carrier provisioning, or outbound submission.
- Network access should be restricted to BigBird-to-gateway traffic on a private or loopback interface.

## Validation

```sh
python -m unittest discover -s integrations/bigbird-messaging/tests -v
python -m pytest -q integrations/bigbird_messaging/test_tools.py
python -m compileall -q integrations/bigbird_messaging
python -m json.tool integrations/bigbird-messaging/tool-manifest.json >/dev/null
python -m json.tool integrations/bigbird-messaging/contract/management-api-v1.json >/dev/null
```

## Staged deployment

```sh
BIGBIRD_ROOT=/opt/bigbird-ai-gateway \
  integrations/bigbird-messaging/scripts/install-staged.sh
```

The script only copies validated assets into `$BIGBIRD_ROOT/.staging/wwcx-messaging`. It does not modify the live tool registry, install secrets, enable control, or restart services.

## Activation gate

A live activation should occur only after inspecting the actual `/opt/bigbird-ai-gateway` registry and configuration conventions, generating separate credentials outside Git, applying least-privileged scopes, validating read-only status, preparing rollback, and approving the service reload. Control should remain disabled until a separate operational approval.
