# Edge1 Operator plugin routing — 2026-08-19

Status: ChatGPT exposure failure reproduced after app publication, plugin workspace installation, and fresh-chat retry. Repository-side plugin package prepared; workspace import/refresh remains the next product-layer gate.

## Verified product-layer evidence

- Existing custom app: `Edge1 Operator`.
- Existing app is published and enabled in the Christmas Island Worldwide ChatGPT workspace.
- Its auto-generated workspace plugin was changed from Available to Installed and the UI confirmed the installation policy update.
- A fresh normal ChatGPT conversation asking `What is Edge1's health?` still reported that `edge1.health` was not exposed in that session.
- The auto-generated plugin details expose the app, but the required `edge1` alias plus implicit routing Skill are not part of that generated app-only package.
- Current OpenAI documentation separates app publication, plugin installation, and plugin-packaged Skills; plugin installation alone does not grant a missing app dependency binding.

## Prepared repair

This branch adds a source-controlled `edge1-operator` plugin package:

- `.app.json` binds alias `edge1` to the existing published workspace app ID.
- `.codex-plugin/plugin.json` packages the app plus Skill.
- `edge1-operator-router` maps ordinary Edge1 questions to the narrowest of the existing 16 bounded tools.
- `allow_implicit_invocation: true` preserves the required natural-language UX.
- No new MCP server, tunnel, credentials, shell authority, or host listener is introduced.

## Acceptance

After the workspace imports or refreshes this plugin source and installs it, start a fresh normal ChatGPT conversation and ask:

`What is Edge1's health?`

Pass requires a real live `edge1.health` result. Do not accept an @mention, app picker, cached status, or documentation answer as completion.
