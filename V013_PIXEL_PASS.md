# v0.13 Pixel Pass

This pass is based on the supplied 920×1640 neon poker reference and the 402×874 emulator screenshot.

Mobile changes only:
- table stage shortened to restore the reference aspect ratio;
- opponent seats/avatars/cards reduced to the reference proportions;
- hero seat/avatar compressed while preserving width;
- board moved lower; pot/chips kept above it;
- timer and selected-action HUD cards reduced;
- action buttons, presets, amount controls, slider and auto-action bar tightened;
- header reduced so top seats no longer visually fight with navigation;
- game logic and API are unchanged.

Most geometry can still be changed from CSS variables at the top of `static/component-ui.css`.
