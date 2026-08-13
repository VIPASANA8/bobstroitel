# Compact mobile Poker8 HUD

## Scope

Refine only Poker8 v2 at viewports up to 780 px. Desktop presentation and poker action semantics remain unchanged.

## Layout

- Keep the top summary with `TO CALL`, `POT`, and `BET`.
- Remove the separate `minus / amount / plus` row; amounts remain visible in preset and action buttons.
- Keep the gradient slider and five presets: `MIN`, `1/2 POT`, `POT`, `2/3 POT`, `MAX`.
- Remove the `BB` suffix from summary, preset, and action amounts inside this mobile HUD only.
- Increase preset readability without increasing total HUD height.
- Keep the four-action grid below the slider.
- Move the HUD slightly upward while preserving the existing bottom reserve.

## Turn information

- Center the pink 30-second timer in the free pocket between the left viewport edge and the viewer avatar.
- Put the cyan turn context in the corresponding right pocket.
- Size the turn context to its text with compact padding; keep the text size unchanged and cap the width for long player names.
- Neither element may overlap the viewer avatar, its glow, cards, or the HUD.
- Center both context lines: acting player above, latest action or invested amount below.

## Slider feedback

- Use a continuous cyan-to-violet-to-pink-to-gold track.
- While the thumb moves, no preset is highlighted.
- After one second without input, highlight only the nearest matching preset.
- A direct preset click highlights immediately.
- Reduced-motion mode removes motion only; the settled selection remains visible.

## Verification

- Cover removal of the stepper row, gradient track, centered turn context, and one-second settled state with regression tests.
- Verify at 360 by 800 and at the 780 px breakpoint.
- Verify mobile-to-desktop resizing restores desktop controls.
