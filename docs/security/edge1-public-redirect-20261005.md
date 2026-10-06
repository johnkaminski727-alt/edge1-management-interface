# Edge1 public visitor redirect

2026-10-05 UTC. Public IPv4 89.126.248.191 ports 80 and 443 return HTTP 302 to
https://www.ww.cx/ for all ordinary requests. Incoming path and query are discarded.
The public vhosts expose no management files or upstreams. Private WireGuard
10.77.0.1:443 keeps the existing authentication, health and management gateway.
The existing valid edge1.ww.cx certificate secures public HTTPS.

HTTP /.well-known/acme-challenge/ is the only exception; it serves ACME token
files from /var/www/edge1-acme, with 0755 parent directories. Both Edge1 and NTP
certificate renewals use that webroot to avoid competing for port 80. Certbot
reconfigure validates each change against the staging CA before saving it.
The NTP deploy hook remains; the added 60-edge1-nginx-reload hook validates and
reloads Nginx only when Edge1's certificate is actually renewed.

Firewall: the existing ens3 port-80 ACME rule is retained. Added only a TCP/443
allow rule on ens3 to 89.126.248.191, comment Edge1 public HTTPS redirect. Other
firewall/security rules remain authoritative, so banned sources may be dropped.
IPv6 has no advertised public redirect endpoint in this deployment.

External HTTP and HTTPS checks from Business159 returned 302 with the exact
Location. HTTPS check verified the certificate without ignoring errors.
Private GET /healthz remains 200; private GET / remains the existing 302 login
redirect. Nginx config validation and reload passed.

Source: deploy/nginx/edge1-public-redirect.conf and deploy/certbot/60-edge1-nginx-reload.
Backup: /var/backups/edge1-public-redirect/20261005T040436Z contains original
renewal configs and UFW rule file. Rollback: remove the new public Nginx enabled
symlink, validate and reload Nginx, then remove only the public ens3 TCP/443 rule
with UFW. Restore old certificate renewal configs only after port 80 is no longer
occupied; remove the added Edge1 deploy hook. Never restore an entire old UFW
rule file over later bans. Existing private vhost was not edited.
