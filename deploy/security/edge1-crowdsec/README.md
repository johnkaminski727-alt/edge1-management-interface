# Edge1 CrowdSec enforcement

Install locations on edge1:

| Repo path | Installed as |
|---|---|
| `sbin/edge1-crowdsec-{bootstrap,enforce,forward}` | `/usr/local/sbin/` (0750 root) |
| `sbin/edge1-crowdsec-verify.py` | `/usr/local/sbin/` (0755 root) |
| `systemd/*.service`, `systemd/crowdsec-firewall-bouncer.service.d/` | `/etc/systemd/system/` |
| `nft/*.nft` | `/etc/edge1/crowdsec/` (0640 root) |

Start order (systemd `Requires=`/`After=`): `edge1-crowdsec-bootstrap` -> `edge1-crowdsec-enforce`
-> `crowdsec-firewall-bouncer` (set-only; fills `crowdsec-blacklists`/`crowdsec6-blacklists`)
-> `edge1-crowdsec-forward`.

The isolated `edge1-guard` chains exempt `wg0` and UDP/51820, so VPN administration
is never blocked by CrowdSec decisions.

All three scripts are idempotent: `edge1-crowdsec-verify.py` accepts both a fresh
bootstrap and an already-enforced state and fails on any unexpected chain, rule,
hook or priority. Before 2026-10-11 a restart of the bootstrap failed its own
check (it required exactly one chain), which took down the bouncer and left the
IPv4 blocklist empty for ~43 h (ENG-021).

Note: the edge1 agent shell cannot use netlink; run `nft`/`wg` via
`systemd-run --quiet --pipe --wait --collect <cmd>` when inspecting from it.
