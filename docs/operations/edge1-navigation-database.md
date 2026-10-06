# Edge1 database-backed navigation

The runtime source of truth for the Edge1 Operator Shell is
`/var/lib/edge1-navigation/navigation.sqlite3`.

The browser never reads SQLite directly. `edge1-navigation-export.service`
exports a fail-closed, navigation-only JSON document atomically to
`/var/www/edge1-status/operator-shell/navigation.json`. Every Edge1 page uses
that same generated document through the shared operator shell.

Key module fields include label, section, sort order, browser/candidate/runtime
routes, availability, authorization metadata, visibility, `enabled`, and
`theme`. Disabled rows stay in SQLite but are omitted from browser JSON.
Theme can be `inherit`, `light`, or `dark`; the shared shell applies the active
module's database theme without page-specific rail markup.

Runtime commands:

```
sudo -u wwadmin edge1-navigation-db list --all
sudo -u wwadmin edge1-navigation-db disable <module-id>
sudo -u wwadmin edge1-navigation-db enable <module-id>
sudo -u wwadmin edge1-navigation-db theme <module-id> light|dark|inherit
```

Database changes trigger the exporter through a systemd path unit, with a
one-minute timer as reconciliation backup. The unified publisher prevalidates
the database-generated registry and restores it after publishing assets, so
repository JSON cannot silently replace runtime database state.

Navigation metadata does not grant authorization. Route enforcement remains
owned by nginx/application authentication and the relevant backend gates.
