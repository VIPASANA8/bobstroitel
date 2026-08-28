# Responsive Call/Bet Summary Spacing

## Problem

On mobile, the `УРАВНЯТЬ / СТАВКА` strip is pinned to `top: 41%`. The pot and board use different responsive anchors, so resizing the table changes the two surrounding gaps independently. Measurements at 374px width show the strip overlapping the pot by 2.8px at 640px height and producing 13.6px / 24.3px gaps at 874px height. The same geometry is used in seated and spectator layouts.

## Design

Keep the existing pot, board, and strip markup. During the existing mobile UI sync, read the rendered pot bottom, board top, strip height, and table-center origin. Set the strip's top coordinate so its vertical center equals the midpoint between the pot bottom and board top. Recalculate through the existing render and window-resize sync path; do not add a second resize system.

If the pot, board, or strip is hidden, has no measurable height, or leaves no valid interval, clear the dynamic coordinate and retain the current CSS position as a fallback. Desktop behavior is unchanged.

## Verification

Add a browser regression covering 640, 720, 800, and 874px viewport heights in both seated and spectator modes. At each size, both gaps must be non-negative and equal within one device pixel. Keep the existing center-stack ordering and overlap checks. Update the static-asset cache key, run the regular suite and focused browser tests, then verify the public production assets and readiness endpoint after deployment.
