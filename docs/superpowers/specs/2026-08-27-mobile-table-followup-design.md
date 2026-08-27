# Poker8 mobile table follow-up

## Scope

This pass fixes four mobile-only presentation defects without changing poker rules,
online state, desktop layout, seat order, or action submission:

1. countdowns must read as rings around the relevant avatar;
2. the `УРАВНЯТЬ / БАНК / СТАВКА` summary must not overlap a seat or action;
3. tables with 2–5 players need intentional, symmetric geometry;
4. the duplicate green `?` control must be removed.

## Root causes

- The ready countdown is appended to `.felt` and centered on the board. The turn
  timer uses a full `conic-gradient` layer above the avatar, so its centre still
  covers the avatar image.
- On mobile, `.action-panel` spans the viewport as a fixed transparent layer, but
  `.v038-hud-summary` keeps its desktop `top:4px` absolute position. It therefore
  lands directly below the header and collides with the top seat.
- `v040` computes layouts for each player count, but the later mobile rules in
  `v038` overwrite every visual seat with the six-player coordinates using
  `!important`. Lower counts receive a truncated six-player arc.
- `v037` already provides the working purple hint control. `v038` appends a second
  green `#mobileHelpButton` with no handler.

## Design

### Avatar countdown rings

Both countdown types use one visual rule: a 3–4 px conic ring outside the avatar,
with a transparent centre. The seconds remain in a small badge outside the circle,
so neither the ring nor the number obscures the avatar.

- The turn timer remains attached to the acting player's `.avatar-wrap`.
- The ready/start countdown moves from the felt to the seated viewer's avatar.
- A spectator has no controlled avatar, so the existing compact table-centred
  countdown remains as a fallback only in spectator mode.
- Ready and turn countdowns cannot be active at the same time; no stacking or
  priority control is added.

### Summary rail

On mobile, the summary becomes a compact fixed rail in the centre corridor between
the two 88 px edge-action columns. It sits above HERO and below the board, uses
three equal numeric columns, and has no pointer events. Its width is derived from
the action width plus a small gap rather than from hard-coded device widths.

Desktop keeps the existing action-panel summary.

### Player-count geometry

HERO remains at bottom centre. Opponents occupy equal-angle points on the same
upper semicircle:

| Total players | Opponent angles |
| --- | --- |
| 2 | `90°` |
| 3 | `135°, 45°` |
| 4 | `150°, 90°, 30°` |
| 5 | `180°, 120°, 60°, 0°` |
| 6 | `180°, 135°, 90°, 45°, 0°` |

The existing `p8-player-count-N` classes select the coordinate set. No new runtime
state or geometry engine is introduced. Spectator layouts and all desktop rules
remain unchanged.

### Header cleanup

Remove creation and styling of `#mobileHelpButton` from `v038`. Keep the existing
purple hint button from `v037`, including its current behavior. Seat/observe controls
can then use the released header width.

## Verification

- Source tests lock the absence of the duplicate help button and the presence of
  count-specific mobile coordinate rules.
- Playwright checks 2–6 player layouts at 360×800 and 402×874: symmetry, ordering,
  equal-angle spacing, HERO at bottom centre, and no seat/summary intersection.
- Playwright verifies that ready and turn rings are children of the correct avatar,
  their centre is transparent, and the seconds badge sits outside the avatar.
- Existing action, sizing, online-flow, desktop breakpoint, and full test suites
  must remain green.

## Acceptance criteria

- No countdown covers an avatar image for a seated mobile player.
- `УРАВНЯТЬ / БАНК / СТАВКА` intersects neither a seat HUD nor an edge action.
- Every 2–6 player seated layout is symmetric and follows the angle table above.
- Only one `?` button remains in the mobile header: the working purple hint button.
- Desktop rendering and poker mechanics are unchanged.
