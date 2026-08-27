# Poker8 mobile layout production pass

## Scope

This pass fixes six mobile-only presentation defects without changing poker
rules, action submission, online seating state, desktop layout, or element
readability:

1. replace the animated queued-button halo with a quiet status treatment;
2. place pot chips above the pot amount;
3. keep every opponent HUD inside the viewport for 2–6 players;
4. pin the chat/rankings utility group to the right edge of the header;
5. raise the board and `УРАВНЯТЬ / БАНК / СТАВКА` rail;
6. keep the dealer puck clear of the avatar timer.

## Root causes

- The queued controls use rotating conic-gradient rings and two simultaneous
  glows, which makes a passive status compete with active game actions.
- Mobile overrides place `.pot-total` above `.pot-chips`, while both elements
  were previously designed to share a horizontal row.
- `--p8-arc-radius:46vw` locates the extreme seat centres about 15 px from a
  360–374 px viewport edge, but a seat HUD is 90 px wide.
- `margin-left:auto` is applied to the chat button inside
  `#mobileHeaderUtility`, not to the utility group itself.
- The board remains at 49% and the summary rail is anchored only 158 px above
  the bottom, leaving both too close to HERO and the action controls.
- The timer badge and `.dealer-button` both occupy the avatar's right side.

## Design

### Quiet queued state

Keep two controls because they express two different things: `В очереди` is a
disabled status and `Отменить` is the available action. Remove the rotating
ring and broad halo. Mark the status with a small static green dot and a subtle
green border; keep cancel as a stable violet outline. Reduced-motion needs no
special queued-state override because the queued state has no animation.

### Safe equal-chord arc

Retain the existing angle sets for 2–6 players and only constrain their shared
radius:

```css
--p8-seat-safe-inset:50px;
--p8-arc-radius:min(46vw,calc(50vw - var(--p8-seat-safe-inset)));
```

The 50 px inset covers half of the 90 px HUD plus glow tolerance. Because every
point is still projected from the same radius, equal chord spacing and symmetry
remain intact at every player count. HUD, avatar, card, and text sizes do not
change.

### Header ownership

The header remains one flex row. Menu and connection dot stay left, seat status
stays in normal flow, and `#mobileHeaderUtility` receives `margin-left:auto` so
its chat and rankings buttons are always the rightmost group. The child chat
button no longer owns row spacing.

### Central vertical stack

On mobile the central order is:

```text
POT CHIPS
POT AMOUNT
BOARD
SUMMARY RAIL
HERO CARDS / HERO
```

Chips move above the pot without changing their size. Pot, board, and summary
move upward as one composition. The summary remains between the 88 px edge
action columns and keeps `pointer-events:none`.

### Dealer and timer

The timer ring remains around the avatar and its numeric badge remains on the
right. The dealer puck moves to the lower-left outside the avatar on mobile,
giving both indicators fixed, non-overlapping homes without conditional jumps.

## Verification

- Source-contract tests lock the new queued state, header ownership, safe
  radius, central ordering, and dealer/timer sides.
- Playwright checks 2–6 players at 360×800 and 402×874: all visible seat HUDs
  remain inside the viewport, chord spacing remains equal, and symmetry holds.
- Playwright checks chips above pot, pot above board, board above summary,
  summary above HERO, right-aligned utilities, and non-intersecting dealer/timer.
- The existing full Python suite, focused mobile E2E suite, and JavaScript
  syntax checks remain green.

## Acceptance criteria

- No opponent HUD or active-state glow is clipped by the viewport.
- Queue status is legible but visually quieter than game actions.
- Chat and rankings are the rightmost header controls.
- Chips, pot, board, and summary have the agreed vertical order and no overlap.
- Dealer and timer never intersect.
- Poker mechanics, action targets, HUD/card dimensions, and desktop rendering
  are unchanged.
