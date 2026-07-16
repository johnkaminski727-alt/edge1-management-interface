# Mobile Responsive Rules

Date: 2026-07-16

## Principle

Adapt by available layout width and interaction mode, not user-agent string alone.

## Desktop

- Use dense rows and multi-column layouts.
- Allow side-by-side search, result list, and detail panels.
- Support keyboard navigation.
- Show longer excerpts inline.

## Tablet

- Use two-pane layout where width allows.
- Collapse detail below results on narrower widths.
- Keep search and filters easy to reach.

## Phone

- Use one column.
- Render search results as cards.
- Collapse filters.
- Use large touch targets.
- Avoid horizontal scrolling.
- Show source and classification clearly on every card.

## Small Screen Safety

Future write-capable actions should be harder to trigger on small screens:

- fewer visible dangerous actions
- stronger confirmations
- explicit source/context display
- read-only default mode

