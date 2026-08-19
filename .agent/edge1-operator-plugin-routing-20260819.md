# Edge1 Operator plugin routing — 2026-08-19

Status: live Edge1 MCP/tunnel/app lower layers remain accepted, but ordinary ChatGPT tool exposure is still failing. Plugin version 0.1.1 passed the live ChatGPT upload validator; after adding it, the admin surface still resolved to the pre-existing app-only `Edge1 Operator` plugin and a fresh normal chat again reported that `edge1.health` was not exposed. A collision-avoiding 0.2.0 plugin package is now prepared with a distinct plugin identity and distinct packaged Skill name.

## Verified product-layer evidence

- Existing custom app: `Edge1 Operator`.
- Existing app is published and enabled in the Christmas Island Worldwide ChatGPT workspace.
- Its generated app-backed plugin is set to Installed for the workspace.
- The generated plugin detail page shows the required `Edge1 Operator` app, but no packaged Skill section.
- Standalone workspace Skill `edge1-operator-router` exists with Workspace/All access; the admin table still showed 0 invocations and an Aug 18 update date during this investigation.
- Plugin 0.1.0 upload reached ChatGPT validation but failed because `policy.products` is unsupported.
- Plugin 0.1.1 corrected the schema to `policy.allow_implicit_invocation: true` only and received `Plugin successfully uploaded` from ChatGPT.
- After the user selected Add plugin, the visible plugin details still resolved to the existing app-generated plugin ID `plugin_asdk_app_6a84c1e678708191b3e8f00e886be802` rather than a separately identifiable routed plugin package.
- A fresh normal ChatGPT conversation asking `What is Edge1's health?` still reported that `edge1.health` was not exposed and no Edge1 plugin was available.
- Admin plugin search for `edge1` returned no indexed result even though the direct generated-plugin URL remains accessible.
- The user-level Plugin Directory currently presents a workspace billing warning (`Team plan failed to renew`, update payment details before Aug 23, 2026). This is a potentially relevant availability gate, but causation for Edge1 plugin exposure is not proven and no billing action has been taken.

## Collision-avoiding repair

Plugin version 0.2.0 deliberately separates the workflow plugin from the existing app-generated plugin and standalone Skill:

- plugin package name: `wwcx-edge1-live-operator`;
- display name: `WW.CX Edge1 Live Operator`;
- packaged Skill name: `wwcx-edge1-live-router`;
- `.app.json` still binds alias `edge1` to the existing published workspace app ID;
- Skill dependency remains the bounded `edge1` MCP alias;
- `policy.allow_implicit_invocation: true` is the only policy key;
- the original app, MCP service, tunnel, credentials, listeners, DNS, firewall, and authentication are unchanged;
- no generic shell tool is introduced.

## Next acceptance edge

Upload 0.2.0 as a distinct workspace plugin. Before testing chat, confirm the resulting plugin detail page is named `WW.CX Edge1 Live Operator` and visibly includes both the packaged `wwcx-edge1-live-router` Skill and required `Edge1 Operator` app. If ChatGPT instead collapses the archive back into the generated app-only plugin, treat that as product-layer evidence rather than retrying the same package.

Then start a fresh normal ChatGPT conversation and ask:

`What is Edge1's health?`

Pass requires a real live `edge1.health` result. Do not accept an @mention, app picker, cached status, or documentation answer as completion.
