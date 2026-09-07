# Cashier and Mobile Navigation Polish Design

## Goal

Finish the shared POKER/CUBE profile experience without introducing a separate CUBE profile: reuse the CASH cashier layout, adapt its labels and colors for CUBE, add direct game links in both headers, and add mobile swipes only between each game and its own cashier.

## Product behavior

### CUBE cashier header and tabs

- Keep the existing two-slot tab layout.
- The active tab reads `USDT-касса` and its badge reads `$$$`.
- The second slot remains the same width but has no text and no click, keyboard, or tab behavior.
- The CUBE cashier continues to use the existing CUBE color theme.

### Cashier summary cards

- In CUBE mode, replace the existing `За столами` balance card with a visually prominent `Играть` control that opens `/cube`.
- In CUBE mode, `Ожидает вывода` displays only the USDT value; no CASH conversion is shown.
- In POKER mode, `Ожидает вывода` displays USDT as the primary value and CASH as the secondary value.
- All other wallet values continue to use the current shared-wallet conversion logic.

### Cross-product headers

- On the CUBE game page, the left header link reads `← В POKER` and opens `/`; the right CUBE brand opens `/cube`.
- In the POKER profile/cashier, the left header link reads `← В CUBE` and opens `/cube`; the right POKER brand opens `/`.
- In the CUBE profile/cashier, the left header link reads `← В POKER` and opens `/`; the right CUBE brand opens `/cube`.
- Header controls are semantic links and remain keyboard accessible.

### Mobile swipes

- Swiping left on the POKER lobby opens `/static/profile.html?app=poker#cash`.
- Swiping right on the POKER CASH cashier opens `/`.
- Swiping left on the CUBE game opens `/static/profile.html?app=cube#cash`.
- Swiping right on the CUBE USDT cashier opens `/cube`.
- No swipe switches directly between POKER and CUBE.
- A swipe must be predominantly horizontal and pass a minimum distance threshold so normal scrolling is preserved.
- Gestures that start on links, buttons, form controls, or the interactive cube canvas are ignored.
- Desktop mouse drags do not trigger navigation; the gesture is enabled for touch input.

### CUBE result strip

- Move the `КУБИК ГОТОВ` result strip to the top edge of the dice card.
- Move the cube scene lower and preserve a clear gap between the strip and cube faces.
- Keep the current card structure and state text; this is a layout-only change.

## Implementation shape

- Reuse existing profile and cashier DOM nodes. Do not add a new CUBE profile screen or change the two-column tab markup.
- Extend the existing product-state rendering in `static/profile.js` and the current CUBE/POKER styles.
- Add one small shared touch-swipe helper and initialize it from the POKER lobby, CUBE game, and cashier pages with page-specific destinations.
- Keep navigation as normal same-origin links so browser history and direct URLs behave normally.
- Make no API or database changes.

## Accessibility and failure behavior

- The blank CUBE profile slot is inert and omitted from keyboard navigation.
- The CUBE `Играть` card exposes link semantics and an accessible name.
- Swipe navigation is only an additional shortcut; all destinations remain reachable through visible links and bottom navigation.
- If touch gesture detection is unavailable, visible navigation continues to work unchanged.

## Verification

- Add focused source/UI tests for product-specific labels, values, destinations, disabled tab behavior, swipe initialization, and CUBE result-strip placement.
- Run the affected automated test suites and the full project suite required by the repository.
- Visually verify desktop and mobile layouts for POKER lobby/CASH cashier and CUBE game/USDT cashier, including the non-overlapping result strip.
- After verification, merge the feature branch into `main`, push `main`, deploy using the repository's existing production procedure, and run the production health check.
