# One-command acceptance / evidence runner

`tools/acceptance_evidence.py` runs a fixed set of safe repository checks and writes a private timestamped evidence directory containing per-check JSON, a summary, and SHA-256 hashes.

Default source-only run:

```bash
python3 tools/acceptance_evidence.py --output-root /var/lib/wwcx-deployment-evidence/edge1-acceptance
```

Optional live read-only run on Edge1:

```bash
python3 tools/acceptance_evidence.py --live-read-only --output-root /var/lib/wwcx-deployment-evidence/edge1-acceptance
```

The live flag runs the repository-owned deterministic `server/edge1_snapshot.py` collector added by PR #375. That collector already bounds host, service, network, repository, Operations API, BigBird, firewall-summary, and recent-critical-error observations. The acceptance runner accepts no arbitrary command, URL, service, path-to-execute, or shell fragment.

An `attention` result is evidence to review, not permission to mutate production. Apply/rollback remains a separate authorized workflow.
