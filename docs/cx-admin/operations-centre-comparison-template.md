# CX Admin Operations Centre Comparison

Use this record only after running the verified CX Admin route inventory. Do not infer routes, titles, permissions, data sources, or capabilities.

## Inventory reference

- Inventory file:
- Inventory generated at:
- Verified admin root:
- Reviewer:
- Required BigBird route present: `/admin/bigbird-operations-console.php`

## Surface A

- Verified route:
- Actual page title:
- Navigation label:
- Authentication check:
- Required role or permission:
- Owning subsystem:
- Data sources and APIs:
- Read-only information shown:
- Actions available:
- Unique cards, links, or workflows:
- Direct links to other consoles:
- Source fingerprint:

## Surface B

- Verified route:
- Actual page title:
- Navigation label:
- Authentication check:
- Required role or permission:
- Owning subsystem:
- Data sources and APIs:
- Read-only information shown:
- Actions available:
- Unique cards, links, or workflows:
- Direct links to other consoles:
- Source fingerprint:

## Overlap analysis

- Shared status cards:
- Shared APIs or data sources:
- Duplicate actions:
- Duplicate navigation links:
- Conflicting labels:
- Permission differences:
- Unique functionality that must be preserved:

## Decision

Select exactly one:

- [ ] Consolidate into one canonical Operations Centre.
- [ ] Retain one parent Operations Centre with clearly named subsystem consoles.
- [ ] Retire one surface and redirect it to the canonical page.

### Canonical top-level route

- Route:
- Label:
- Required permission:

### Retained child consoles

| Route | Label | Scope | Permission |
|---|---|---|---|
| | | | |

### Redirects or retired routes

| Existing route | Destination | Reason |
|---|---|---|
| | | |

## Preservation checklist

- [ ] Every unique operational capability is represented in the chosen design.
- [ ] There is only one unambiguous top-level Operations entry.
- [ ] BigBird is clearly identified as a subsystem when retained separately.
- [ ] Desktop and mobile navigation use the same registry.
- [ ] Unauthorized links are hidden.
- [ ] Direct-route authorization remains enforced.
- [ ] Every retained route resolves.
- [ ] Redirects preserve bookmarks without weakening authorization.
- [ ] Rollback steps are documented.

## Validation evidence

- PHP syntax checks:
- Navigation integrity test:
- Authenticated smoke test:
- Desktop navigation result:
- Mobile navigation result:
- Rollback verification:
