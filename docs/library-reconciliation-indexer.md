# Library reconciliation indexer

`tools/library_reconciliation_index.py` creates a non-destructive inventory for loose WW.CX / Edge1 / Project Big Bird artifacts.

It records SHA-256, filename/path, date, inferred or reviewed project/evidence type, repository representation, canonical retained record, duplicate relationship, deletion eligibility, and unresolved status.

Unknown material always defaults to `review-required` / `unresolved`. A file is only marked `eligible-after-independent-verification` when a reviewed mapping explicitly supplies all three of: a duplicate target, a canonical retained record, and confirmation that unique value has already been reconciled.

The tool has no delete, move, rename, or overwrite capability.

Example:

```bash
python3 tools/library_reconciliation_index.py /path/to/export \
  --mapping reviewed-map.json \
  --json reconciliation-index.json \
  --csv reconciliation-index.csv
```

The optional mapping is keyed by SHA-256 so filename changes do not silently transfer a disposition to different content.
