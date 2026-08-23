# Ava Imagination and Visual Generation

Status: source prepared; live Edge1 activation not yet performed  
Date: 2026-08-23

## Objective

Give Ava a private visual workspace in the WW.CX administrator chat with first-class support for image generation, clip art, diagrams, variations, transparent-background assets, and image editing.

## Architecture

```text
Authenticated browser
  -> ww.cx admin request queue
  -> visual request marked with visual:create / visual:edit
  -> signed claim_visual lane
  -> Edge1 ava-visual-worker.service
  -> existing OPENAI_API_KEY from the Private AI gateway environment
  -> OpenAI image endpoint
  -> signed binary upload to ww.cx private visual store
  -> authenticated /admin/ai/visual.php viewer
  -> inline image card in Ava chat
```

Generated image bytes never travel through the normal browser queue JSON. The queue carries only bounded request metadata and sanitized visual metadata.

## Credential boundary

The visual worker does not create, copy, print, or persist a second OpenAI credential. It reads `OPENAI_API_KEY` from the existing Edge1 Private AI gateway environment through the systemd environment file. Source code contains only the environment-variable name.

The worker also reuses the existing signed browser-worker identity for private asset exchange with `ww.cx`.

## Visual modes

- `image` — general image generation.
- `clipart` — reusable isolated artwork, transparent background requested by default.
- `diagram` — explanatory graphics with a landscape default and emphasis on legible labels and hierarchy.
- `edit` — uses a private attachment or previously generated visual as the source image.

Edits require both `visual:create` and `visual:edit`. Generation requires `visual:create`.

## Private asset flow

The website provides two worker-only signed endpoints:

- `/api/ava-visual-asset.php` — fetch an authorized current user's image attachment or prior visual for an edit.
- `/api/ava-visual-store.php` — receive generated binary data plus bounded metadata in the `AVAV1` envelope.

Both use the existing browser-worker HMAC identity, timestamp/skew checks, body hashes, and nonce replay protection. Visuals are stored under the existing per-user private AI context directory and are streamed to the browser only through the authenticated `/admin/ai/visual.php` route.

Metadata records request id, visual mode, model, dimensions, size, SHA-256, prompt hash, creation timestamp, and edit parent where applicable. The private index may retain the prompt; browser responses do not expose it as visual metadata.

## Queue isolation

Normal chat workers claim only non-visual requests. The visual worker claims only `claim_visual` jobs. This prevents a visual request from being forwarded to the read-only chat gateway and makes visual generation independently deployable and reversible.

Visual leases are at least 300 seconds because image generation can exceed the ordinary chat lease. Normal chat lease behavior is unchanged.

Completion validation remains fail-closed:

- normal requests must complete in `read-only` mode and may not inject visual assets;
- validated visual requests must complete in `visual-create` mode and must include at least one sanitized visual asset.

## Model configuration

Default image model: `gpt-image-2` via `BB_OPENAI_IMAGE_MODEL`.

The model name is non-secret configuration and can be changed without changing the credential path.

## Source assets

Edge1 repository:

- `server/ava_visual_generator.py`
- `server/ava_visual_worker.py`
- `deploy/ava-visual-worker.service`
- `tests/test_ava_visual_generator.py`

Website repository:

- visual controls and inline rendering in Ava chat;
- private authenticated visual viewer;
- signed worker asset fetch/store endpoints;
- visual queue routing and completion sanitization.

## Activation boundary

Source preparation and CI are safe repository work. Live activation requires an authenticated Edge1 write path because it must install/enable `ava-visual-worker.service` and verify its environment access. The currently mounted Edge1 operator is read-only, so no live service installation or restart is represented as completed.

Before activation:

1. merge reviewed source changes;
2. verify the website visual endpoints are deployed;
3. verify `/etc/bigbird-ai-gateway.env` exists without printing any values and that the service user can receive `OPENAI_API_KEY` through systemd;
4. install only `deploy/ava-visual-worker.service` as the corresponding systemd unit;
5. daemon-reload and start the visual worker;
6. verify no new public listener is created;
7. run one bounded image-generation acceptance request, then one clip-art request and one edit request;
8. verify returned images remain admin-authenticated and request/user isolation is preserved.

## Rollback

Disable and stop only the Ava visual worker, then restore the previous website release. Do not alter the existing Private AI gateway, its OpenAI credential, DNS, firewall, TLS, PBX, or ordinary browser worker as part of visual rollback.
