# WW.CX Edge1 Live Operator plugin

This workspace plugin has a deliberately distinct plugin identity from the app-backed `Edge1 Operator` listing. It binds the existing published Christmas Island Worldwide `Edge1 Operator` app to the local alias `edge1` and packages the uniquely named `wwcx-edge1-live-router` Skill for implicit natural-language routing.

The distinct plugin and Skill names avoid colliding with the existing generated app-only plugin and the pre-existing standalone `edge1-operator-router` workspace Skill.

The app remains the authority for live access and exposes only the existing bounded Edge1 tools. This plugin does not create a second MCP server, duplicate the Secure MCP Tunnel, or add shell execution.

## Acceptance target

A fresh normal ChatGPT conversation asking:

`What is Edge1's health?`

must invoke the live `edge1.health` tool without an @mention or manual app selection and return the current Edge1 result.

## Workspace import

Upload the plugin archive as a distinct workspace plugin named `WW.CX Edge1 Live Operator`, set its installation policy for the workspace, and keep the required `Edge1 Operator` app enabled. The uploaded plugin must show the packaged `wwcx-edge1-live-router` Skill as well as the required app before acceptance testing.
