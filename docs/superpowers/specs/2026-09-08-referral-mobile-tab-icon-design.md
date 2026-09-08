# Mobile Referral Tab Icon Design

## Goal

Reduce the width of the referral profile tab on phones without changing its behavior or accessibility.

## Behavior

- At viewport widths up to and including 580 px, the referral tab visually displays only `🔗`.
- Above 580 px, the tab continues to display `Рефералы`.
- The tab keeps the accessible name `Рефералы` at every width.
- Selection, keyboard navigation, lazy loading, sharing, and referral calculations remain unchanged.

## Implementation

Keep both visual variants inside the existing `#referralModeTab`. CSS under the existing `@media(max-width:580px)` breakpoint swaps their visibility. No JavaScript behavior changes are required.

## Verification

- A source regression test checks both labels and the 580 px visibility rules.
- Browser tests verify `🔗` at 580 px and `Рефералы` at 581 px while the accessible tab name remains `Рефералы`.
- Run the focused profile suites, JavaScript syntax check, and the full non-E2E regression suite before deployment.
