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


## Daily-use upgrades

The visible From selector lists registered full addresses and organizations, with draft-only readiness when outbound is not commissioned. Replies keep the original receiving identity. Organization names in the prepared footer follow the canonical sender. Signature details can be remembered per sender in the private preferences DB; unset mailing addresses are left blank and must be supplied by the operator. A commercial draft also accepts an unsubscribe URL.

Drafts autosave after a 1.5 second pause, with unsaved/failed status. Edits invalidate the prepared state. Inbox controls persist unread/archive/tags without mutating or deleting source mail; filtering by domain, private John addresses, shared role addresses and quarantine is available. Private/company views organize an operator-only surface: shared-user authorization is not enabled by these views. Contact links open a prefilled directory search; the installer patches only the startup-query behavior in the live Contacts asset.

AVA summary/reply buttons explicitly submit bounded thread excerpts to the existing configured AVA model through its server-side signed gateway. No additional retrieval or web research is requested. Suggestions are plain text; using a reply requires an operator click and creates an editable draft. Neither operation sends or modifies mail. The signed relay configuration is held in `/etc/wwcx/mail-room-ava.env`, not browser assets. It is a limited bridge implementation using the existing relay signing identity; future relay key separation remains a maintenance improvement.

Activity currently shows prepared-not-sent records. Provider queued/sent/bounce receipts require first-domain outbound commissioning and must not be inferred from a prepared draft.

ClamAV indexes and scans attachments from verified native raw archives using a periodic service/timer. Unknown, stale-scanner, oversized, scan-limit and encrypted-file outcomes remain blocked or quarantined. No attachment download/release endpoint exists. The scanner checks at most 25 archives per run from the latest bounded 10,000 archive records, and revisits checks after an hour. Provider-native archives require the equivalent archive/index path during commissioning. A clean scanner result is not a delivery or download approval.
