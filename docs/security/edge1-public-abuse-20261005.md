# Edge1 public redirect abuse protection

Activated 2026-10-05 UTC. TARGET: edge1.

Ordinary visits still receive 302 to https://www.ww.cx/. Public HTTP and HTTPS
share source-address leaky-bucket limits: 2 requests/second with 20 burst slots.
Sensitive paths (admin, login, WordPress, phpMyAdmin, .env, .git, edge1-ops, api,
actuator and cgi-bin) additionally share 6 requests/minute with 5 burst slots.
Excess is rejected as 429 with Retry-After: 60. Limits use the actual connection
address, never forwarded headers. Loopback, host public IP and WireGuard subnet
are exempt; the private VPN vhost has no public limiter directives.

The redirect runs in a named location reached by try_files after the limit phase;
a direct return in the original location would bypass Nginx limit_req.
The root directory is intentionally empty; no management files or upstreams are
reachable. ACME challenge location remains exempt. Existing TLS remains valid.

Only actual limit_req REJECTED responses enter edge1-public-abuse.log. The log
contains source IP, final status, limiter status, sensitivity flag and time; no
query, cookie, user-agent or raw request path. The Fail2Ban filter matches only
429 REJECTED entries. Ten such rejections in 120 seconds trigger a native ban.
Normal redirects and occasional sensitive-path visits do not count as failures.

Native persistent Fail2Ban durations: 172800, 604800, 2592000, 63115200 seconds
(48h, 7d, 30d, 730.5d), final tier repeats. Existing three-year database retention
applies; only this jail's history counts, independently of SSH. Native Fail2Ban
may accelerate detection for known offenders. Public bans affect TCP/80 and
TCP/443 to 89.126.248.191 only. The custom UFW action has no whole-host fallback.
Ban/release events are in /var/log/fail2ban.log. Existing Nginx log rotation covers
the new abuse log. IP-based bans can affect users sharing a public address.

Operator review: fail2ban-client status edge1-public-abuse
Operator release: fail2ban-client set edge1-public-abuse unbanip ADDRESS
Release is an operator override; native Fail2Ban may clear that IP's retained
ban record, so it is not the same semantics as the private cookie release.

Validation: isolated Nginx on loopback test ports, public-trust exemptions disabled
only in the test configuration, confirmed ordinary 302; 12 sensitive probes
produced 6 redirects and 6 rejections; subsequent 100-request burst produced 86
rejections. Limits were shared across both test listeners. ACME requests returned
200 despite exhausted buckets, and rejected responses had Retry-After: 60.
Fail2Ban regex matched generated rejections. UFW dry-run confirmed the rule's
public-destination/two-port scope without mutating the firewall. Full Nginx and
Fail2Ban configuration tests passed; live action, limits and jail were read back.
Public HTTP/HTTPS ordinary visits were externally verified from Business159;
VPN health remained 200. No live client ban was injected.

Sources: deploy/security/edge1-public-abuse. validate_runtime.py exercises an
isolated real Nginx instance and writes test logs/results in its source directory;
run a disposable copy of that directory when testing. Existing public redirect
source deploy/nginx/edge1-public-redirect.conf is synchronized with live config.

Backup: /var/backups/edge1-public-abuse/20261005T041120Z contains original public
vhost and consistent pre-change Fail2Ban DB. Rollback: stop only the new jail via
fail2ban-client stop edge1-public-abuse (releases its firewall bans); remove its
jail/filter/action files; restore public.before.conf; remove the new Nginx common
config; nginx -t then reload Nginx; fail2ban-client -t then reload Fail2Ban. Preserve
current DB/evidence; do not overwrite SSH history with the old backup.
