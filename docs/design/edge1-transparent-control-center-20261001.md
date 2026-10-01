# Edge1 Transparent Control Center Experience — 2026-10-01

## Objective

Make the management resource feel like one coherent Edge1 workspace rather than a collection of separately deployed pages. Authentication, navigation, page context, status semantics, search and read-only safety should be consistent enough that module boundaries become operationally transparent without hiding security boundaries or authority state.

## Research basis

The design intentionally borrows established patterns from mature administrative interfaces and public design systems:

- pfSense treats the dashboard as the primary at-a-glance landing page and exposes configurable status widgets that link into relevant configuration/status views:
  https://docs.netgate.com/pfsense/en/latest/monitoring/dashboard.html
- OPNsense uses a lobby/dashboard home, layered navigation, and independent widgets; its dashboard framework explicitly ties widget data access to the same ACLs used by pages:
  https://docs.opnsense.org/manual/gui.html
  https://docs.opnsense.org/manual/dashboard.html
  https://docs.opnsense.org/development/frontend/dashboard.html
- USWDS side navigation guidance emphasizes showing the current page, keeping hierarchy shallow, and testing for excessive depth; breadcrumbs and alerts are stable components used to preserve orientation and status:
  https://designsystem.digital.gov/components/side-navigation/
  https://designsystem.digital.gov/components/overview/
  https://designsystem.digital.gov/components/site-alert/

## Edge1 design rules

1. One authenticated namespace
   - Browser-facing private modules live below `/edge1-ops/`.
   - Authentication boundaries are enforced server-side; navigation never grants authority.
   - No module should force the operator to reason about loopback ports or HMAC credentials.

2. One shell
   - A shared registry renders desktop navigation, mobile navigation, jump/search and ToolBox.
   - The WW.CX/Edge1 brand is always a link back to the Control Center home.
   - The active module is shown consistently and can be resolved from the current browser route if explicit module metadata is absent.

3. One source of navigation truth
   - Accepted browser routes come only from the canonical navigation registry.
   - Duplicate legacy navigation inside modules is removed as modules join the shared shell.
   - A registry failure falls back only to an authenticated Edge1 route.

4. Transparent module transitions
   - Moving between Operations, Security, Network, Contacts and AVA should preserve the same shell, visual tokens and session.
   - A module may have its own task-specific tabs, but not a competing global navigation system.

5. Status at a glance, detail on demand
   - The Control Center presents the important current state first.
   - Specialist pages own deeper operational detail.
   - Normal healthy/live state should not visually compete with warnings, pending acceptance or degraded state.

6. Safety remains explicit
   - Read-only/mutation state remains visible.
   - Unknown is never rendered as healthy.
   - Upcoming or unaccepted modules remain visible but non-navigable.
   - AVA planning/approval/execution boundaries remain independent of browser navigation.

7. Deep links remain first-class
   - Authenticated URLs should be bookmarkable and directly reloadable.
   - An expired session returns through the existing WW.CX authentication handoff and back into Edge1.
   - Browser routes must not depend on navigating through the landing page first.

## Phase 3L implementation

- Make the shell brand a direct Control Center-home link.
- Generate a hierarchical `Edge1 / Section / Module` breadcrumb.
- Auto-resolve the active accepted module from the current route when page metadata is absent.
- Correct the shell failure fallback to `/edge1-ops/status/` rather than the retired unauthenticated-style path.
- Remove the duplicate legacy module navigation from Contacts & Relationships.
- Keep Contacts/AVA route promotion separate from implementation until browser acceptance.

## Acceptance standard

The experience is not considered transparent until:

- no accepted menu item returns 404;
- all accepted specialist pages share the same authenticated session and shell;
- direct reload of every accepted URL works;
- expired-session behavior is consistent;
- desktop and mobile both identify the current module;
- Contacts and AVA display no competing legacy global nav;
- no browser route exposes loopback implementation details, HMAC material or mutation authority;
- a registry outage leaves a safe authenticated escape route rather than a broken or public-style link.
