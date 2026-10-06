# Edge1 source and live reconciliation — 2026-10-06

The repository and live interfaces were preserved before reconciliation in
/var/backups/edge1-git-reconcile-20261006T035248Z/repository-and-live.tar.gz.
This archive retains superseded source files without leaving obsolete variants
in the active source tree.

Contacts source now includes the live entity grouping, merge UI, empty-state
artwork, current layout, spacing and mobile rules. Existing source favicon links
were retained. Mail Room and static DNS/VPN interfaces are now source controlled.
The Operations Center source includes the live Mail Room link.

Runtime databases, session stores, credentials, generated navigation exports,
DNS/VPN telemetry JSON, and the generated daily summary are not source assets.
They remain runtime data; their observed UI files were preserved in the archive.
The navigation database remains authoritative.

Publication guard: tools/edge1_operator/check_ui_publication.py
The Operations Center publisher invokes it before changes and records afterward.
It requires committed source, a revision descending from the recorded checkpoint,
and no unexpected live static-file drift. Baseline state is local to Edge1 at
/var/lib/edge1-ui-publication/baseline.json. Missing baseline fails closed.
Other deployment entrypoints must adopt this guard to gain the same protection.

Workflow: edit source, review/test, commit, push, then publish. Reconcile live
emergency edits into source before publishing. Never reset/clean a dirty working
tree to solve deployment drift. A rollback needs its own explicit reconciliation;
the guard deliberately blocks older histories.

No services were restarted and no contact/DNS/VPN runtime data was changed.
