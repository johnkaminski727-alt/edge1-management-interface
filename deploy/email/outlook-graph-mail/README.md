# Edge1 Outlook Graph Mail intake

Read-only delegated Microsoft Graph intake for `spiritcreekgardens@outlook.com`.
The app registration must support personal Microsoft accounts and public-client/device-code flow.
Only delegated `Mail.Read` is granted; `offline_access` is requested so Edge1 can refresh the delegated session unattended.
No sending or mailbox mutation permission is used.

The exact provider MIME is preserved under `/var/lib/wwcx-mail-room/imports/outlook-spiritcreekgardens`.
Per-folder delta state and OAuth refresh material are private under `/var/lib/wwcx-mail-room/outlook-graph`.
