# Manual Mail Room

Open `https://edge1.ww.cx/edge1-ops/mail-room/` through the existing private Edge1 access and sign in through the normal portal handoff. The Operations Center exposes a Mail Room card; the operator menu exposes Mail Room beside existing modules. Contacts and AVA keep their order.

The inbox lists persisted authoritative correspondence. Search matches literal subject or sender text; the optional recipient filter matches the original receiving address. Search is paged at 25 messages. Open a message to read its thread as plain text. Email HTML never runs and this view does not open attachments.

Choose **Draft a reply** or **New draft**. **Save draft** preserves incomplete drafts in a private SQLite store on Edge1. **Saved drafts** lists the latest 100 records. **Prepare for review** saves first, then calls the existing signed preparation API to apply sender identity and signature policy. Required signer/title/mailing address must be completed. Preparing does not send. Editing a prepared draft invalidates the visible preview until it is prepared again. Drafts are not shared with AVA automatically.

Initially only the local commissioning canary exists. Real provider intake is pending provider credentials and separate per-domain commissioning. The UI displays this explicitly. Sending remains disabled at the gateway and SMTP layers; the browser bridge exposes no send endpoint.

## Runtime boundary

`server/mail_room_http.py` runs as `wwcx-mail-gateway` on 127.0.0.1:8117. nginx accepts the browser routes only on its existing private listener and checks the existing Edge1 session before forwarding API calls. A separate root-private proxy key prevents unsigned direct loopback access; the gateway HMAC key stays server-side. Draft mutations additionally require the exact Edge1 origin, a custom request header and JSON. Mail content, IDs, cookies and query strings are excluded from bridge access logs. Private API responses are not cached.

Deploy the approved root-owned staged release with `deploy/messaging/install-manual-mail-room.py --release /opt/wwcx-email/releases/SHA`. This installer preserves the existing nginx, navigation, portal card page and any prior Mail Room assets/unit in a timestamped private backup under `/var/backups/wwcx-email-recovery/`. It does not change the dirty live checkout, Postfix policy, provider credentials or outbound gates. The draft DB is `/var/lib/wwcx-mail-room-drafts/drafts.sqlite3` (directory 0700, DB0600).

To roll back the UI, stop/disable `wwcx-mail-room`, restore the backed-up nginx main configuration and navigation/card files, validate nginx and reload. Preserve the draft database. An existing installation also backs up its service, assets and nginx snippet.

Validation: `python3 -m unittest discover -s tests -p test_mail_room_http.py` covers proxy denial, cross-origin/request-header/content-type denial, persistent drafts, prepared-only results, absence of send, private DB permissions and bounded input. Existing mail gateway correspondence and client isolation checks remain applicable.
