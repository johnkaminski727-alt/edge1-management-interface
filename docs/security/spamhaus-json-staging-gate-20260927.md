# Spamhaus JSON staging gate — 2026-09-27

**Status: parser and offline fixture tests only; filter activation remains prohibited.**

Edge1 operator Assignment 206 verified official `drop_v4.json` and `drop_v6.json` respond HTTP 200 and use line-delimited JSON plus one publication metadata record. Assignment 207 downloaded them into an automatically deleted root-only temporary directory, found 1710 unique IPv4 and 91 IPv6 CIDRs (1610 and 85 after collapse), checked publications aged 22.3h and 46.8h, successfully ran `nft --check --file` on a temporary candidate, and verified the production `inet bigbird_spamhaus` table remained absent. These are time-bound results, not ongoing feed-health claims.

This change adds `tools/networking/spamhaus_feed_candidate.py`, a strictly offline line-delimited JSON parser and candidate renderer, and `tests/validate_spamhaus_json_candidate.py`, deterministic fixtures covering duplicate/adjacent prefixes, JSON errors, non-global addresses, wrong families, freshness, missing metadata, and candidate rendering. Both IPv4 and IPv6 are required. It accepts metadata timestamps within 72h and up to 15m of positive clock skew. The candidate includes explicit input/forward drop hooks at priority -110. It does **not** call nft, access the network or save a production file.

On Edge1, once this branch is checked out in a separate clean test clone, run `python3 -m unittest discover -s tests -p validate_spamhaus_json_candidate.py -v`; optional separately approved runtime staging can then download current official feeds, call the parser into a disposable root-only directory, and run `nft --check --file` without applying rules.

**Critical:** existing `tools/networking/spamhaus-nft-update.sh` still uses legacy text/eDROP feeds and **executes `nft -f`**. Do **not** run it or `tools/networking/install-spamhaus-filter.sh` in production until replaced by a reviewed check-only-by-default updater and accompanied by a versioned rollback and SSH connectivity plan. Do not activate the Spamhaus service/timer or the unrelated `nftables.service` from this staging change. Existing UFW, CrowdSec and kernel rules continue unchanged.
