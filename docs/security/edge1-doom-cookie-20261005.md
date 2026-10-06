# Fuck You Cookie (TM) — Edge1 defensive web marker
Activated 2026-10-05 UTC.

## Behavior
Four qualifying explicit denials in a rolling-reset 10-minute counting window trigger a block.
Durations in seconds: 172800, 604800, 2592000, 63115200
(48 hours, 7 days, 30 days, 730.5 days).
Attempts during an active block do not advance the tier or extend its deadline.
After expiry a fresh four-denial sequence advances the retained tier.
The final tier repeats at 730.5 days.

Qualifying reasons: missing authorization scope or invalid CSRF on protected routes.
Missing/expired sessions, ordinary login redirects, unknown URLs, closed mutation gates,
health, logout, VPN-account provisioning and assertion exchange are excluded.
This is deliberately narrower than counting all 401/403 responses.

No new listener, production login pathway, public web port, decoy or SSH service.
HTTPS remains bound to 10.77.0.1:443.
Existing session authentication and mutation gates remain authoritative.
Nginx overwrites trusted attribution headers from its real connection address;
client-supplied forwarded IPs are not trusted.
Protected status/contacts pages consult the existing session gateway, which enforces
the marker and address block. Browser authentication responses remain generic.

## Marker and evidence
Cookie: __Host-wwcx_doom, signed random identifier, Path=/, Secure, HttpOnly, SameSite=Strict.
Requested lifetime: 63115200 seconds; browser policies can shorten it.
Deletion does not delete server address history. A retained signed marker also carries
a block to another address. IP/marker correlation is not proof of a person's identity.
No resurrection, cross-domain tracking, device files or background device access.

SQLite state: /var/lib/wwcx-edge1-ops/doom-cookie/evidence.sqlite
Signing key: same directory/signing.key (0600; never publish or print).
Evidence records timestamps, trusted source IP, path without query parameters,
method, bounded user-agent, request ID, decision, tier and expiry.
HMAC chained events detect modifications when verified with the retained key.
They are not immutable against a compromised privileged host; deletion of the tail
needs an independently retained checkpoint to detect.
Block events are local audit alerts, not external email/Slack notifications.
Firewall-dropped traffic cannot receive browser cookies.
This implementation does not change CrowdSec/SSH bans or escalate firewall drops.

## Operator review
Run locally on TARGET: edge1, from /opt/edge1-management-interface:
sudo python3 -m server.edge1_doom_cookie_admin list
sudo python3 -m server.edge1_doom_cookie_admin verify
sudo python3 -m server.edge1_doom_cookie_admin release --subject ID --actor OPERATOR --reason "review explanation"
Release clears the active deadline/strikes, preserving escalation history.

## Rollback
Backup: /var/backups/edge1-doom-cookie/20261005T031725Z
Restore 0-edge1_security_auth_http.py and 1-edge1_security_auth_http_server.py to server/.
Restore 2-edge1-private.conf to the resolved enabled Nginx site.
Remove only /etc/systemd/system/edge1-security-auth.service.d/30-doom-cookie.conf.
Run nginx -t, systemctl daemon-reload, restart edge1-security-auth, reload nginx.
Retain evidence/key for review; do not delete them as part of rollback.

## Acceptance
27 engine/middleware/auth tests passed.
Isolated Nginx probe proved auth_request denies, cookie delivery on the fourth denial
through the error handler, and active-block enforcement; no live client was banned.
Live HTTPS health=200; unauthenticated protected portal=302 to existing login.
Initial activation encountered a source-file permission error; file permissions were
corrected, gateway restarted and live health restored.
