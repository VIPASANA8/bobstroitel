# Poker8 Mobile 6-Max Edge Actions Design

## Goal

Recompose the existing Poker8 mobile table as a portrait-first, native-feeling 6-max interface without reducing the readability of cards, player HUDs, stacks, labels, or action targets. Preserve the existing poker engine, online transport, action semantics, timers, pre-actions, animations, and desktop layout.

The reference viewport is 402 × 874 px. A 360 × 800 px viewport is the mandatory lower-bound acceptance size and must not use whole-interface scaling.

## Scope

This change applies to the existing mobile table at widths up to 780 px. It changes layout, visibility, styling, and bet-sizing interaction. It does not rewrite the table, game engine, WebSocket transport, persistence, settlement, or action validation.

Landscape-specific redesign is outside this pass. The current non-portrait fallback remains available.

## Architecture

Keep the current DOM and rendering flow in `static/index.html` and `static/app.js`. Extend the final Poker8 v2 mobile layer, primarily `static/v038-poker8-v2-cinematic-table.js`, rather than creating a new table implementation or another versioned override.

`static/app.js` remains the source of legal actions, amounts, pre-action state, and action submission. The mobile layer controls where those existing surfaces appear and adds mobile-only sizing-mode interaction. Desktop behavior above the 780 px breakpoint remains unchanged.

No new runtime dependency is required.

## Screen Composition

The portrait screen is one continuous table stage beneath a compact header. There is no permanent lower action dock.

The vertical information order is:

1. five opponent HUDs on one arc;
2. pot immediately above the board;
3. board;
4. temporary bet-sizing controls when open;
5. HERO cards;
6. HERO HUD at the bottom center.

The invisible action panel may remain as a DOM owner for existing controls, but it has no visible panel background, border, reserved height, or dock geometry. Its interactive children are positioned independently.

## Opponent Arc

P1 through P5 lie on one circular arc, not a grid, chevron, pyramid, or percentage-distorted ellipse. Use a shared pixel radius derived from viewport width so horizontal and vertical offsets use the same unit:

- P1: 180°;
- P2: 135°;
- P3: 90°;
- P4: 45°;
- P5: 0°.

The arc uses a 45° angular step, which gives equal chord distance between neighboring HUD centers. The top of the arc remains below the compact header. Side HUDs may overlap or extend beyond the wooden table edge and may be partially clipped by the viewport if necessary to preserve their size.

HERO is excluded from this arc and remains fixed at the bottom center.

## Readability and Dimensions

The mobile layout uses these targets at both required acceptance sizes:

- opponent avatar: 44 px;
- opponent HUD: approximately 90 px wide;
- opponent name: 12 px minimum, single-line ellipsis;
- opponent stack: 16 px, never truncated;
- opponent card backs: approximately 32 × 44 px;
- board cards: approximately 46 × 64 px;
- HERO cards: approximately 50 × 70 px;
- HERO avatar: 48 px;
- HERO name: 13 px;
- HERO stack: 18 px;
- action and confirmation touch targets: at least 48 px, with a 56–64 px preferred height.

Decorative gaps, shadows, and padding compress before any of these readable elements. No `scale()` is applied to the whole interface.

## Header

The mobile header contains:

- menu button and connection dot on the left;
- chat and help buttons on the right.

The icon touch areas remain at least 48 px. The connection state uses only a small state-colored dot. Permanent `connected` text and application/version branding are removed from the game surface.

`ЗАНЯТЬ МЕСТО` is not displayed in the game header. It remains available only inside the spectator seating flow, such as the menu or seating surface.

## Contextual Edge Actions

Action buttons are anchored to the left and right viewport edges, not to the felt or wooden table geometry. They sit in the lower half of the viewport without overlapping HERO.

Buttons have square outer edges against the screen and rounded inner edges toward the table. Color communicates state, not player identity.

When there is no bet facing HERO:

- left: `CHECK`, then `FOLD`;
- right: `BET`, then secondary `ALL-IN`.

When HERO faces a bet:

- left: `FOLD`;
- right: `CALL <amount>`, then `RAISE`.

Unavailable actions are omitted rather than rendered as large disabled controls. During another player's turn, the same context layout continues to expose the existing pre-action behavior. A queued action receives the existing queued indication and is cancelled by the existing invalidation rules when the table state changes.

## Bet and Raise Mode

A tap on `BET` or `RAISE` opens a temporary sizing overlay above HERO instead of immediately submitting an aggressive action.

The overlay contains:

- `MIN`, `1/2`, `2/3`, `POT`, and `MAX` presets;
- the current amount in BB;
- the existing range slider;
- an explicit confirmation button;
- a cancel control.

The five presets remain readable and fit in one row at 360 px. The overlay disappears after confirmation, cancellation, terminal hand state, loss of eligibility to act, or a state change that invalidates its amount bounds.

`ALL-IN` enters the same confirmation flow with the amount set to the legal maximum. It is never sent by the first tap.

## Vertical Bet Gesture

Pressing and dragging upward from the right `BET` or `RAISE` button activates a vertical amount rail along the right viewport edge. Pointer/touch movement selects among legal, deduplicated steps derived from:

- minimum legal amount;
- 2 BB when legal;
- 4 BB when legal;
- 1/2 pot;
- 2/3 pot;
- pot;
- maximum legal amount;
- all-in when distinct from maximum labeling.

The amount nearest the finger is displayed in large text beside the rail. Releasing the pointer only selects the amount and leaves the confirmation overlay open. It never submits the bet. This safe-confirmation rule also applies to an all-in selected through the gesture.

Pointer cancellation restores the last settled amount and keeps the overlay in a safe, unsubmitted state.

## Player States

Player outline colors have semantic meaning:

- neutral: ordinary player;
- cyan: HERO;
- bright green/neon: current active player;
- orange: all-in;
- dimmed: folded;
- muted: disconnected;
- red: critical timer state.

Folded players remain visible at roughly 50% prominence. Their hidden card backs disappear while name and full stack remain readable.

Players still in the hand may show two card backs behind the avatar. The active player is recognizable through glow, highlighted card backs, and a timer ring around the avatar.

The timer is attached to the active player's avatar. The separate floating mobile timer card is removed. HERO uses the same timer treatment when HERO is active.

## Data Flow and State Changes

The existing render cycle continues to provide game and table state to the mobile layer. The sequence is:

1. `static/app.js` renders seats, legal actions, amounts, and queued-action state;
2. the mobile layer maps occupied seats around HERO and applies the six visible arc positions;
3. action rendering selects only the contextually relevant mobile controls;
4. sizing mode reads existing min/max, pot, stack, and slider values;
5. confirmation calls the existing `sendAction` path with the selected legal action and amount;
6. subsequent snapshots close or update transient mobile state when legality changes.

No poker amount, legality, or all-in decision is invented in CSS or duplicated in a separate game model.

## Responsive Rules

At 360 × 800 and 402 × 874:

- retain the target dimensions listed above;
- derive the opponent arc from viewport width using one shared pixel radius;
- reduce decorative spacing before readable content;
- keep edge actions clear of safe-area insets and HERO;
- show sizing controls only while sizing mode is active;
- allow HUD overlap with the table edge instead of shrinking the HUD.

At 781 px and above, the desktop table and action panel remain unchanged.

## Accessibility and Safety

- All interactive targets remain at least 48 px.
- Hidden actions are removed from focus order.
- Opening sizing mode moves an accessible label/state to the sizing surface without forcing keyboard focus away from the current control.
- Confirmation and cancellation are explicit buttons.
- Vertical gesture selection has a tap-and-slider fallback.
- Reduced-motion mode disables nonessential pulses and transitions while retaining state indicators.
- Connection, active-turn, fold, and all-in states are not communicated by color alone; labels, opacity, timer text, or action text remain available.

## Verification

Automated checks cover:

- 6-max seat rotation keeps HERO at visual seat zero;
- opponent HUD centers use the approved circular arc ordering;
- context actions omit unavailable controls;
- no-bet and facing-bet action sets;
- `BET`, `RAISE`, and `ALL-IN` open confirmation mode without immediate submission;
- preset and slider amounts remain within existing legal bounds;
- vertical gesture steps are ordered, legal, and safe on pointer release;
- folded players hide card backs but retain readable HUD content;
- active-player timer is attached to the correct HUD;
- permanent lower action panel and textual connection badge are absent on mobile;
- mobile-to-desktop resize restores the desktop layout.

Browser acceptance checks run at 360 × 800, 402 × 874, and 781 px desktop breakpoint. Existing engine, online transport, table UI state, and mobile online-flow tests must remain green.

## Out of Scope

- rewriting poker mechanics or server contracts;
- changing betting legality or settlement;
- redesigning desktop Poker8;
- adding a new UI framework or gesture dependency;
- implementing a separate landscape composition;
- refactoring unrelated historical versioned style layers.
