# Active Player Glow Design

## Goal

Make the acting player immediately recognizable on the mobile six-max table without adding labels, arrows, rays, or other elements over the felt.

## Visual behavior

- The current player's avatar and identity plate share a strong turquoise glow.
- The glow pulses slowly without flashing or changing element dimensions.
- Cards, player name, stack value, seat accent color, and table layout do not change.
- When the turn changes, the old highlight fades out and the next player's highlight fades in over 180–250 ms.
- With reduced motion enabled, the highlight stays bright but does not pulse.

## State and integration

The presentation reuses the existing active-turn state on the seat card. It adds no new game state, status label, or duplicated turn indicator. The effect remains mobile-only and must not alter the desktop table.

## Acceptance criteria

- Exactly one acting seat is highlighted while a turn is active.
- Both the avatar and identity plate are highlighted together.
- The effect follows every turn transition and clears when no turn is active.
- The highlight remains readable for dimmed and folded seats without restoring unrelated rectangular backplates.
- Existing mobile layout, timer, action context, ready marks, and action-color states remain unchanged.
