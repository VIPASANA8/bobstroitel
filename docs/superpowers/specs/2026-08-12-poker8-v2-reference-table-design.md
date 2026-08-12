# Poker8 v2 Reference Table — Design

## Goal

Bring the mobile six-max poker table on `agent/poker8-v2-mobile-6max` close to the supplied portrait reference while preserving the current game behavior. Replace the reference's top-right settings control with a decorative chat button.

## Scope

This pass changes only the mobile game scene at widths up to 780 px. It does not change the poker engine, API, seat configuration, action handling, desktop layout, or add chat behavior.

The implementation will follow the branch's existing additive visual-pass pattern by loading a new `v037` layer after `v036`. Existing visual passes remain intact so the change is isolated and easy to remove.

## Visual Direction

The mobile viewport should read as one dark, cinematic poker room rather than a stack of interface panels:

- a nearly full-screen vertical table surrounded by a dark wooden rail and subdued wood-room background;
- deep emerald felt with a subtle center falloff, fine texture, and two green neon edge lines;
- six occupied visual positions: one at the top, two on the upper sides, two on the lower sides, and the local player at the bottom;
- compact dark player plaques with seat-specific neon accent colors, an avatar or card-back crown, player label, and stack;
- a centered pot label above the five community cards, with chips below the board;
- the local player's hole cards emerging above the bottom avatar/plaque;
- a compact hamburger control at top left and a matching decorative chat control at top right.

Typography stays condensed, uppercase, and high-contrast. Cyan is reserved for the local player and global controls; opponent accents may use green, purple, orange, and magenta. The background and rail stay quieter than the felt and game information.

## Layout and Components

The existing DOM remains the source of game data and interaction. The new pass may add only presentation-only elements needed by the reference, such as the top-right chat button and decorative rail layers.

The table geometry will be tuned for the branch's target mobile viewports:

- `360 × 800` is the compact baseline;
- `402 × 874` is the tall-phone baseline;
- intermediate widths use fluid dimensions and capped aspect ratios;
- critical game elements must not overlap the viewport edge, the action area, or each other.

The current six-max visual-seat mapping remains authoritative. The hidden seventh seat remains hidden. Player and card contents continue to be rendered by the existing JavaScript.

## Chat Control

The chat button is visual only. It receives an accessible label and button styling matching the top-left menu control, but it does not open a panel, send messages, or alter game state. It must not masquerade as an existing settings action.

## States and Behavior

Pre-hand, active-hand, folded, all-in, active-turn, and showdown states continue to use existing state classes and rendering. The visual pass may refine their colors, opacity, glow, and positioning, but cannot suppress required game information or change click targets.

The existing action controls below the table remain functional and visible when required. The reference guides the table scene; it does not authorize removing betting, ready, history, or other current game actions.

## Accessibility and Resilience

- Text and stack values retain readable contrast over the dark plaques.
- Cards, controls, and required game actions keep usable touch targets.
- The decorative chat button is keyboard-focusable and clearly labelled, but has no action.
- Reduced-motion behavior remains unchanged; no new required animation is introduced.
- The desktop view and widths above 780 px must remain visually unchanged.

## Verification

Verification will include:

1. existing automated tests relevant to the frontend/server still pass;
2. the app loads without console errors;
3. visual inspection at `360 × 800` and `402 × 874` covers pre-hand and active-hand scenes;
4. all six visual seats, the pot, board, chips, local cards, menu, chat button, and action controls remain visible without unintended overlap;
5. desktop layout is checked for regression;
6. the chat button causes no state or navigation change.

## Out of Scope

- functional chat;
- new avatar artwork or downloaded third-party assets;
- poker logic, API, persistence, or bot changes;
- redesign of desktop management panels;
- exact reproduction of copyrighted character imagery from the reference.
