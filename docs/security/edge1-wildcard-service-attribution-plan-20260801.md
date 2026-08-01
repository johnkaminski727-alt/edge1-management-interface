# Edge1 Wildcard Service Attribution Plan — 2026-08-01

## Trigger

The comprehensive listener rerun at `2026-08-01T02:57:26Z` confirmed that TCP `3306`, `8001`, and `8003` are wildcard-bound.

The authoritative public input policy still admits only TCP `80`, TCP `443`, and UDP `51820`, so new public-interface traffic to those three target ports is dropped. The rule `iifname "wg0" accept` nevertheless makes them reachable from every authenticated WireGuard peer.

## Priority

1. MariaDB/systemd socket TCP `3306`.
2. Node TCP `8001` and `8003`.
3. Subsequent least-privilege decisions for WireGuard and listener bind scope.

The audit must identify ownership and consumers before any listener or firewall change is selected.

## Read-only audit scope

The audit may collect:

- target listener lines and all owning PIDs;
- systemd service and socket metadata;
- unit file hashes and only non-secret lifecycle directives;
- process executable, working directory, cgroup and service mapping;
- Node entry-script path, metadata and SHA-256 without reading application content;
- MariaDB configuration file hashes and only bind, port, socket and protocol directives;
- established-connection counts without remote addresses;
- Apache, HAProxy, nginx and systemd references to ports `8001` and `8003`;
- the authoritative nftables input chain.

The audit must not collect:

- process environments;
- database rows, grants, usernames or credentials;
- application configuration secrets;
- complete Node command lines when they may contain tokens;
- remote client addresses;
- journal payloads;
- packet captures or external active scans.

## Decision boundary

A listener may be considered for narrowing only after the following are known:

- authoritative service or socket owner;
- intended local, WireGuard or public consumer;
- reverse proxy or internal dependency references;
- current established-use count;
- configuration source controlling the bind;
- restart and rollback implications.

No database, Node, systemd, listener, firewall, WireGuard or proxy mutation is authorized by this plan.
