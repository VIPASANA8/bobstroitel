# Poker8 v2 Final Mobile Reference — Design

## Goal

Finish the real mobile six-max product so its 360 × 800 game screen closely follows the approved cinematic reference, including the user's two layout corrections. The comparison page was only a disposable mockup; this design applies to the running Poker8 product.

## Approved Direction

Use the reference's complete visual hierarchy rather than isolated decorative details:

1. A dark wood room and thick oval wooden rail frame deep emerald felt with paired green neon edge lines.
2. Five bots and the local player use large reference-style seat silhouettes: two angled card backs, a round avatar medallion, and a separate black name/stack plaque. Portrait images remain deferred, so the existing neutral medallion and future `--profile-avatar-image` hook stay in place.
3. The pot, community cards, chip stacks, wager markers, dealer button, and hero cards remain data-driven and are restyled and repositioned to match the reference.
4. The lower HUD uses the reference hierarchy: call/pot/bet summary, five sizing presets, slider/amount, and three prominent FOLD/CALL/RAISE actions.
5. The table scene uses a restrained perspective tilt: the far rail reads narrower and higher while the near rail reads broader and closer. Seats, plaques, cards, chips, and text receive compensating transforms so values stay legible rather than appearing skewed.

## User Corrections

- Keep the current left menu button exactly as it is; do not redesign or replace it.
- Keep the right-side chat button from the current product, not the settings button shown in the reference.
- Move the slider into the row previously occupied by FOLD/CALL/RAISE.
- Use a stable 2 × 2 action grid inside the HUD: CALL / ALL IN above, dynamic FOLD or CHECK / dynamic BET or RAISE below. Keep the separate bottom reserve completely empty for a future global application menu.
- Enlarge and compose every player seat like the supplied reference, not like the small schematic placeholders from the first mockup.

## Layout Contract

At 360 × 800, the fixed header occupies the top safe strip, the cinematic table fills the upper game region, and the 260 px HUD sits below it without vertical scrolling. The upper seat, hero seat, community cards, pot, chips, wagers, and all five opponent seats stay fully visible. The slider occupies the middle row, the four primary actions use a stable 2 × 2 grid, and the separate 46 px bottom reserve remains empty.

At 402 × 874, the same hierarchy scales without stretching the player plaques disproportionately. Widths above 780 px retain the existing desktop presentation. Desktop-to-mobile resize must initialize the mobile chat and final visual pass correctly.

Perspective applies only to the table scene and its game objects. The fixed header, menu, chat control, lower HUD, and reserved bottom strip remain front-facing and aligned to the viewport.

## State and Interaction Rules

- Existing game state and actions remain authoritative; this pass does not create duplicate poker controls or calculations.
- Active turn, folded, all-in, pre-hand, showdown, and ready states remain visually distinct.
- Existing action buttons keep their behavior and accessibility labels; only their presentation and order within the mobile HUD change.
- CALL, ALL IN, FOLD/CHECK, and BET/RAISE keep fixed slots. Unavailable actions remain visible at 35% emphasis. FOLD is red, CHECK and CALL are cold blue, BET/RAISE is green, and ALL IN is gold.
- ALL IN, including a MAX-sized BET/RAISE, requires a second confirmation click within three seconds. The confirmation uses a draining gold line and respects reduced-motion preferences.
- Preset labels stay bright white. The selected preset remains pink until the amount is changed manually.
- The chat control remains decorative until chat functionality is separately requested.
- The reserved bottom strip contains no poker controls, click targets, or placeholder label.

## Implementation Boundary

Extend the existing final mobile presentation layer rather than rewriting the renderer or earlier passes. Prefer CSS over JavaScript and reuse current DOM nodes. A minimal presentation-only synchronization may add summary labels or reorder existing mobile HUD nodes only if CSS cannot express the reference hierarchy; it must not fetch data, persist state, or alter poker decisions.

No portrait assets, profile API changes, game-engine changes, desktop redesign, settings-button replacement, or future global-menu implementation are included.

## Verification

- Regression tests lock the mobile-only loader, avatar hook, preserved menu/chat controls, state selectors, reserved bottom safe area, and absence of network/game-state logic.
- Browser inspection covers pre-hand and active-hand states at 360 × 800 and 402 × 874, plus desktop width and desktop-to-mobile resize.
- At 360 × 800, the action panel and reserved bottom strip must both fit inside the viewport without document scrolling or clipping.
- The full test suite is run; the known unrelated six-bot-capacity failure is reported separately if it remains the only failure.
