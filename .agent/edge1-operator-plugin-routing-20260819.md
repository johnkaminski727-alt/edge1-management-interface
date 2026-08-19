# Edge1 Operator plugin routing — 2026-08-19

Status: ChatGPT exposure failure reproduced after app publication, plugin workspace installation, and fresh-chat retry. Repository-side plugin package is prepared. First workspace archive upload reached ChatGPT's plugin validator and exposed one packaging-schema defect; that defect is corrected in plugin version 0.1.1.

## Verified product-layer evidence

- Existing custom app: `Edge1 Operator`.
- Existing app is published and enabled in the Christmas Island Worldwide ChatGPT workspace.
- Its auto-generated workspace plugin was changed from Available to Installed and the UI confirmed the installation policy update.
- A fresh normal ChatGPT conversation asking `What is Edge1's health?` still reported that `edge1.health` was not exposed in that session.
- The auto-generated plugin details expose the app, but the required `edge1` alias plus implicit routing Skill are not part of that generated app-only package.
- The source-controlled plugin archive was accepted far enough by ChatGPT to validate the packaged Skill metadata.
- ChatGPT rejected version 0.1.0 because `agents/openai.yaml` placed `products` under `policy`; the validator reported that `policy` may contain only `allow_implicit_invocation`, which must be boolean.

## Prepared repair

The source-controlled `edge1-operator` plugin package now:

- binds alias `edge1` to the existing published workspace app ID in `.app.json`;
- packages the app plus Skill through `.codex-plugin/plugin.json`;
- maps ordinary Edge1 questions to the narrowest of the existing 16 bounded tools;
- declares `policy.allow_implicit_invocation: true` as the only policy key, matching the live ChatGPT validator;
- carries plugin version `0.1.1` so the corrected archive is unambiguous;
- introduces no new MCP server, tunnel, credentials, shell authority, or host listener.

## Acceptance

Upload the corrected 0.1.1 archive to the Christmas Island Worldwide workspace. If ChatGPT accepts the package, install/enable it as required and start a fresh normal ChatGPT conversation asking:

`What is Edge1's health?`

Pass requires a real live `edge1.health` result. Do not accept an @mention, app picker, cached status, or documentation answer as completion.
