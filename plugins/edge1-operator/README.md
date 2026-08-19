# Edge1 Operator plugin

This workspace plugin binds the existing published Christmas Island Worldwide `Edge1 Operator` app to the local alias `edge1` and packages the `edge1-operator-router` Skill for implicit natural-language routing.

The app remains the authority for live access and exposes only the existing bounded Edge1 tools. This plugin does not create a second MCP server, duplicate the Secure MCP Tunnel, or add shell execution.

## Acceptance target

A fresh normal ChatGPT conversation asking:

`What is Edge1's health?`

must invoke the live `edge1.health` tool without an @mention or manual app selection and return the current Edge1 result.

## Workspace import

The plugin must be imported or made available to the Christmas Island Worldwide workspace from this repository source, then installed for the workspace. The required app must remain enabled. If an imported workspace plugin is refreshed, ChatGPT should reload the `.app.json` binding and packaged Skill from the source.
