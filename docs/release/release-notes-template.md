# Release Notes Template

Status: Controlled document
Applies to: Edge1 Management Interface source releases

Copy the template below into the GitHub release description and complete
every section. Delete a section only if it is explicitly "None."

```markdown
# Edge1 Management Interface <version>

Released: YYYY-MM-DD
Commit: <sha>

## Summary

One or two plain-language sentences on what this release is and who it is
for.

## Changes

- <user-visible change>
- <user-visible change>

## Security notes

<None | plain-language description of security-relevant changes; never
include exploit details for issues fixed in this release before operators
have had a reasonable window to update>

## Known limitations

- <limitation carried into this release, or "None known">

## Verification

Artifacts and SHA-256 checksums:

| Artifact | SHA-256 |
| --- | --- |
| <archive> | <checksum> |

Verify with: `sha256sum -c <checksum-file>`

## Upgrade / deployment notes

<Steps or "No special steps"; reference runbooks under docs/handoff/ where
applicable>
```

Keep release notes free of credentials, private paths that reveal
operational detail beyond what the repository already documents, personal
information, and unredacted diagnostics.
