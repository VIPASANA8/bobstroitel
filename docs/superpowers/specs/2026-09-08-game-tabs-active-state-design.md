# POKER / CUBE Active Tab Visual Design

## Goal

Make the selected game in the fixed bottom POKER / CUBE switcher immediately recognizable while preserving the existing interface structure, geometry, placement, responsive layout, and navigation behavior.

## Scope

Only `static/game-tabs.css` will change. The HTML, active-state class assignment, links, JavaScript, tab order, panel dimensions, border radii, spacing, fixed positioning, safe-area behavior, and mobile clearance remain unchanged.

## Visual System

Both tabs use the same selected-segment treatment:

- active label: `#FFFFFF`, weight `700`;
- active icon: the product accent color;
- active surface: a subtle accent-tinted translucent background;
- active border: a visible translucent accent border;
- active depth: a very weak inset accent glow that reinforces selection without competing with primary CTA buttons;
- inactive label and icon: `#747985`;
- inactive surface: transparent, without an accent border or bright glow.

POKER uses `#B58CFF` for the icon and accent, `rgba(181, 140, 255, 0.12)` for the surface, and a border within the requested 0.40–0.50 alpha range.

CUBE uses `#B7FF26` for the icon and accent, a surface within the requested 0.10–0.12 alpha range, and a border within the requested 0.35–0.45 alpha range.

The shared outer switcher stays dark, retaining clear contrast with either active segment.

## Implementation Approach

Keep the shared inactive and active declarations in `.game-tab` and `.game-tab.is-active`, then apply the two accent palettes through the existing `.game-tab-poker.is-active` and `.game-tab-cube.is-active` selectors. Target the child icon separately so active labels remain white while icons retain their product colors.

No new elements, classes, assets, animations, transitions, or JavaScript will be introduced.

## Verification

- Add a focused CSS contract test that checks the requested active and inactive colors, surfaces, borders, and label weight.
- Confirm the existing POKER and CUBE markup still assigns `is-active` and `aria-current="page"` correctly.
- Run the focused test and relevant existing game-tab/mobile-layout checks.
- Render both routes at a phone viewport and visually confirm that the selected segment is obvious, the inactive segment is secondary, and the switcher geometry has not changed.

