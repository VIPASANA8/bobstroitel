# The layer stack: what is in it, and how to take it apart safely

Twenty-eight files inject styles into the table page, and several of them
also reassign app.js's own functions. The last one to speak wins, and which
one that is depends on load order and selector length together — neither of
which was written down anywhere. Four bugs in a single day came out of that,
all with the same shape: a rule meant for one surface reached the other.

This is the working file for taking layers out. It records what was measured,
what each measurement can and cannot prove, and what has actually been
removed so far. Add to it as you go; a number here beats a memory of one.

## Load order (this is not the order of the names)

```
index.html static tags:  auth-client → online-transport → component-ui →
                         app → table-guide → chat-format → online-table → v039
component-ui.js appends: v015 v016 v018 v019 v020 v022 v023 v024 v025 v026
                         v027 v028-ready-phase v032 v037
v028-ready-phase appends: v031           (with its own stale buster, see below)
v037 appends:            v038 → v040 → v041   (v041 on v040's load event)
```

Two consequences worth keeping in mind:

* **v039 executes before every appended layer.** It is a static tag, so at
  equal specificity v038 beats it on source order. That is why the desktop
  layer needs three-class selectors where two would look sufficient — it has
  been the direct cause of two fixes (the table picture sized to the window,
  the page's floor).
* **The busters differ per file** — v031 carries `?v=pot-wings-1` and six
  layers carry none. Static is served `no-cache` with an ETag, so this does
  not strand anybody (see below); it just makes the version in a URL a poor
  guide to what is loaded.

## What collides

Measured by (element, property), because same-selector duplication is rare
here — what is everywhere is the same element reached by selectors of
different lengths from different files.

| element | layers claiming it |
|---|---|
| `.card {width}`, `.card {height}` | 9 |
| `.seat-stack {font-size}`, `.seat-name {font-size}`, `.action-grid {gap}` | 8 |
| `.table-frame {height/padding/min-height}`, `.seat {width}`, `.player-avatar {width}`, `.felt {inset}`, `.pot-total {top}` | 7 |

Geometry properties claimed by 4+ layers: **137**. By 3+: **213**.

`!important` density — the share of declarations that can only win by
shouting. 100% means the file has no other tool:

```
v016 100%   v018 100%   v019 100%   v020 100%   v026 100%   v028 100%
v031 100%   v032  99%   v039  98%   v035  97%   component-ui.css 93%
v027  92%   v023  86%   v036  81%   mobile.css 64%   v038  63%
```

## Who reassigns app.js's functions

Seven layers wrap `window.syncComponentUi`, and **all seven chain** — each
captures the previous and calls it. Not dead code, but a seven-deep decorator
that runs on every snapshot:

```
component-ui → v026 → v027 → v028 → v032 → v035 → v038 → v040
```

`window.syncComponentSeatLayout`: component-ui → v032 → v040.

The ones that **replace** rather than chain are where dead code hides:

| function | assigned by | outcome |
|---|---|---|
| `wagerPointForPlayer` | v015, then v031 | v031 does not delegate and loads later — **v015's version is unreachable** |
| `togglePendingAction` | v015 only | live |
| `renderMobileHud` | v020 only | live (app.js calls it) |
| `renderGame` | v025 only | live |
| `renderMobileSelectedCard`, `renderPersistentActionButtons` | v016 only | live |

## Measuring: what each method proves, and what it does not

Three methods were tried on the live table. Only the third is worth much on
its own, and none of them is proof by itself.

1. **Same selector declared later** — found almost nothing (`fully answered
   by later layers: none`). Layers do not repeat each other's selectors; they
   reach the same elements by different ones.
2. **Does the selector match anything on a live table** — cheap, and
   misleading. Five layers matched zero elements (v015, v020, v022, v023,
   v024) and *not one of them was dead*: two replace live functions, two
   build their DOM on demand, one carries the branding. **Do not delete on
   this signal.**
3. **Does the declaration survive into the computed style** — the useful one.
   Blind to custom properties, and to any state not on screen when it ran
   (showdown modal, ready phase, a seated player's controls). **Not** blind
   to pseudo-elements, which is what this file said for most of the day and
   was wrong about: `getComputedStyle(el, '::before')` reads them fine. Two
   dead rules sat in v039 an extra half-day on the strength of that.

   And it answers a subtly different question than it looks: the probe
   *fetches* each file and matches its selectors, so it reports what a layer
   would do **if it were loaded**. v035 and v036 scored 93/10 and 22/0 that
   way while being loaded by nobody at all. Check the page's own script list
   first — `[...document.querySelectorAll('script[src*="/static/v0"]')]` —
   and only then ask what a layer's rules are doing.

4. **Move a layer's `<style>` to the end of `<head>` on a live page and diff
   the computed styles.** The dry run for "what if this loaded last", and
   the only way to see what a layer is *holding back* rather than what it
   contributes. It is how the v039 move below was called off before it
   shipped.

   Its diff **nominates candidates; it does not convict them.** Two ways it
   misleads, both paid for on 2026-08-29:

   * *Consequence, not cause.* Move a layer, the felt changes size, and
     everything positioned in percentages of the felt moves with it. Half
     that diff's entries were things the layer never declares.
   * *Percentages have no fixed computed value.* `.felt`'s
     `height:calc(100% - 50px)` read as "loses" because moving the layer
     changed the frame's padding, so 100% was 100% of a different box. It
     was the winner all along -- `.felt` is `position:relative`, so the
     `inset` beside it offsets the box without stretching it, and that
     height is the only thing giving the felt a height. Deleting it put the
     felt 23px through the bottom of the table on the live site.

   So: nominate with the dry run, convict with the net, and never judge a
   percentage by its computed value.

5. **Anything with a `transition` reads at its start value in the browser
   pane.** The pane's tab reports `document.visibilityState === "hidden"`
   even when fronted, so CSS transitions never advance: a seat carrying
   `transition:transform 320ms` shows `matrix(1, …)` for as long as you care
   to wait, whatever the rule says. Half an hour went into "the avatars do
   not scale" before that was the answer -- they scale fine.

   Finish them before measuring:

   ```js
   el.getAnimations().forEach(a => a.finish());
   ```

For JavaScript there is no probe. Read the file.

### Snapshot, taken 2026-08-29 on the live table

`matched declarations / how many survive into the computed style`, from a
real page — bots-only room, watching, mid-hand.

| layer | lines | desktop 1526 | phone 390 | JS behaviour | verdict |
|---|---|---|---|---|---|
| v015-fixes | 75 | 0/0 | 0/0 | replaces `wagerPointForPlayer` (dead), `togglePendingAction` (live) | **partly dead** — the wager override went, 2026-08-29 |
| v016-fixes | 265 | 4/0 | 2/0 | replaces two renderers (live) | keep, CSS worth re-checking in the action-panel state |
| v018-fixes | 33 | 1/1 | 1/1 | style only | keep (one live rule) |
| v019-center-polish | 79 | 24/7 | 19/10 | style only | keep |
| v020-fixes | 110 | 4/1 | 0/0 | replaces `renderMobileHud` (live) | keep |
| v022-balance-topup | 312 | 0/0 | 0/0 | builds a modal on demand | **broken online, see below** |
| v023-brand-balance-fix | 83 | 0/0 | 0/0 | sets the page title and badge (live) | keep — the markup still says "Poker Trainer v0.14" |
| v024-ready-phase | 353 | 0/0 | 0/0 | ready countdown, builds DOM | keep, re-measure in the ready phase |
| v025-showdown-compare | 393 | 19/1 | 0/0 | replaces `renderGame`, builds a modal | keep, re-measure at showdown |
| v026-seat-status-layout | 118 | 1/1 | 1/1 | chains `syncComponentUi` | keep |
| v027-compact-seats-controls | 338 | 72/9 | 49/24 | chains `syncComponentUi` | keep |
| v028-ready-phase | 444 | 48/1 | 48/19 | chains `syncComponentUi`, syncs badges, appends v031 | **merged** from v028+v029+v030, 2026-08-29 |
| v031-pot-cluster-mobile-fix | 105 | 6/0 | 0/0 | replaces `wagerPointForPlayer` (live, wins) | keep; fix its cache buster |
| v032-mobile-sixmax | 308 | 141/32 | 82/11 | chains both sync functions | keep — note 32 of its declarations win on **desktop** |
| ~~v035-pixel-pass~~ | 264 | — | — | — | **deleted 2026-08-29 — nothing loaded it** |
| ~~v036-prehand-pass~~ | 105 | — | — | — | **deleted 2026-08-29 — nothing loaded it** |
| v037-reference-table | 158 | 41/19 | 37/17 | loader for v038/v040/v041 | keep |
| v038-cinematic-table | 1855 | — | — | the table itself | split by platform, eventually |
| v039-desktop-parity | 694 | — | — | desktop geometry | move into the chain so it loads last |
| v040-dynamic-seats | 549 | — | — | the seat ring | keep |
| v041-turn-clarity | 149 | 7/3 | 2/1 | style only | keep |

### What the merge kept, on purpose

The three files became three IIFEs in one file, in the order they used to
load, each still appending its own `<style>`. The cascade between them is
decided by that order, so folding them into a single block by hand is
exactly how such a merge changes what it says it does not.

Two contracts inside are read from outside, and would be easy to lose if
this is ever pulled apart again:

* the body class `v028-prehand-center-ready` — v038 styles the hero's avatar
  and everybody's ready check off it;
* the `<script>` tag at the very bottom, which is the only thing that loads
  v031 — the wager geometry every chip flies by.

## v039 now loads last (done, 2026-08-29)

The dry run below is what called this off the first time, at 50 changed
properties. After the dead two-class geometry came out -- the seat ring, the
felt's paint, the frame's padding/overflow/shadow, `.felt::before`,
`.table-glow` -- the same dry run measured **3**, all of them this file's
`.panel` rule claiming `.action-panel`, which v036 and v038 actually paint.
Scoping that rule with `:not(.action-panel)` took it to **0**.

The move itself is not a move of the script. v039 is a static tag, so its
JavaScript has to keep running early: it is what puts `poker8-desktop-v2` on
`<body>`, and every desktop rule in every other layer keys off that class.
Only its `<style>` goes last, by re-appending the same element on `load` --
same node, end of `<head>`, so desktop geometry is simply the last word.

What this buys: the three-class selectors this file needed to beat v038 on
source order are no longer load-bearing. They can come down to two, one rule
at a time, each verified the same way. Not done yet -- the arms race is over,
the disarmament is a separate afternoon.

## The dry run that called it off first (measured, 2026-08-29)

The plan was to load v039 last so the desktop layer stops needing
three-class selectors to beat v038 on source order. Dry run first: on the
live table, its `<style>` was moved to the end of `<head>` and every
computed property compared before and after.

**50 properties changed across 79 elements.** Not paint — geometry. Seats
jumped to mirrored positions (seat-1 from `left:1166px` to `left:98px`), the
felt changed size and shape, the frame changed padding and overflow.

The reason is worth keeping: v039 still carries the *pre-v038* desktop
table, and it has been losing that argument for as long as v038 has existed.
Loading it last would resurrect it. What changed, by element:

| element | properties v039 declares and loses today |
|---|---|
| `.seat-0` … `.seat-5` | top, left, right, bottom (its own `--seat-N-x/y` ring; v040 owns the ring) |
| `.felt` | width, height, background-image, border-radius, box-shadow, border-color |
| `.table-frame` | padding, box-shadow, overflow |
| `.table-center` | width, top, left, right, bottom, transform |
| `.street-splash` | top, left, right, bottom |
| `.action-panel` | background-image, box-shadow, border-color |

The split inside v039 is clean: its **two-class** rules
(`body.v014.poker8-desktop-v2 …`) are the old table and are dead, because
every table carries `poker8-v2-sixmax`; its **three-class** rules
(`…poker8-v2-sixmax.poker8-desktop-v2 …`) are the live ones. So the order of
work is the other way round from the plan: delete the dead two-class
geometry first, and only then is the move a safe move.

Careful with the two-class rules that are *not* geometry — the topbar, the
brand mark, `.panel`/`.history-card`/`.online-chat-panel` — those win today
and are the only thing styling some of it.

## Where this stands, and what is left

After one day: **19 layer files where there were 23**, 19 scripts on the
page where there were 21, and about 460 lines gone. Every step was run
against the static suite and the browser net before it shipped -- except
one, which is why the net exists and why the log above has a revert in it.

What is left, in the order it should be done:

1. **The rest of v039's two-class geometry.** The felt's size and inset and
   the frame's border, radius and background all win today. They cannot be
   deleted; they have to be *moved* -- into the three-class block, where
   they already belong -- one declaration at a time, net on each. Only when
   the two-class block holds nothing the table needs is the move below safe.
2. **Then the move**: v039 into the appended chain, last. That is what ends
   the three-class arms race for good.
3. **v038 is 1855 lines serving two platforms.** Splitting it by surface is
   the biggest remaining reduction, and the one most likely to need its own
   safety net first.
4. **Even out the cache busters** so a version in a URL means something.
   Nothing is stranded (statics are `no-cache` with an ETag), it is only
   confusing.
5. **The trainer.** Half this stack was written for `app/legacy.py`, which
   production mounts nowhere. Deciding whether that app is coming back would
   settle the fate of v015, v020, v022, v024 and v025 in one go, rather than
   one careful measurement at a time.

## The centre cluster does not fit a short felt (open, 2026-08-29)

The ui scale has a floor now (0.82), and on the window this came from --
1067x632, a 964x458 felt -- it took the avatars from 88px to 72, the seat
boxes from 134 to 110, and the pot's chips off the board entirely (65px of
clearance where they used to sit across it). The pot label and the board are
no longer overlapped by anybody's name plate.

What is left is arithmetic that scaling cannot solve. On that felt the top
seats' plates end at 273 and the bottom seats' begin at 448: a free band of
175px. The centre cluster -- chips, amount, board, stacked -- is 201px tall
at that scale. It does not fit, so the chips run 33px into the top-centre
seat's plate.

Options, none of them taken yet:

* a tighter factor for the cluster alone on short felts (needs its unscaled
  height, or the feedback loop is obvious);
* dropping the chips below the amount, which reverses a deliberate reading
  order (chips, amount, board -- the phone's);
* letting the board overlap the felt's lower band instead, which is where
  the bottom seats live.

## Bugs found while auditing, not bloat

* **The "+" on your own stack cannot work online.** v022 posts to
  `/api/profiles/{profile_id}/top-up`, which exists in `app/legacy.py` — the
  local trainer, which production never mounts. Online the route is
  `POST /api/profiles/play-top-up`. Either point v022 at it or take the
  affordance off the seat; today it is a live button with a 404 behind it.
* **The cache busters are uneven, and it matters less than it looks.** v031
  is appended with `?v=pot-wings-1`, its own; six more (v015, v016, v018,
  v019, v022, v023) are appended with no query string at all. I first wrote
  that down as "cached forever" and that was wrong: `RevalidatedStatics` in
  app/online.py sends `Cache-Control: no-cache` with an ETag on everything
  under /static, so a browser must revalidate each file on every load and a
  changed file comes back changed. Measured on the live site. The busters
  are belt to that braces -- worth evening out, not load-bearing.
* **`tests/e2e/test_mobile_online_flow.py` is red** — it waits for
  `p8-can-ready` after sitting down and never gets it. It fails the same way
  at `07848bd`, so it predates the 2026-08-29 work.
* Production serves only `/`, `/table`, `/monitor` (`app/online.py`).
  `app/legacy.py` — the trainer — is mounted nowhere, yet the client still
  ships and runs the layers written for it.

## The safety net

```bash
python -m pytest tests/e2e/test_the_table_holds_together.py -m e2e
```

Nine cases: three rooms × three viewports, ~30s. It asserts what a screenshot
would have shown — no sideways overflow, the felt inside its frame, the
picture painted the width of the frame, seats and their cards on the felt, a
watching viewer getting the watching layout and an invitation, the pot and
the action bar centred, and the phone never taking the desktop's scale.

It was checked by putting two of the day's faults back; both passed at first,
and both assertions had to be sharpened before they failed. Do that with any
assertion added here — an unproven check is worse than none, because it is
believed.

Run alongside it, every time:

```bash
python -m pytest tests -q --ignore=tests/e2e --ignore=tests/load
```

## Work log

| date | change | verified by |
|---|---|---|
| 2026-08-29 | Stage 0: the net above | 9 cases green; two faults re-introduced and caught |
| 2026-08-29 | v015's `wagerPointForPlayer` removed — v031 replaces it later without delegating, so it could never run | static suite + the net + the live page |
| 2026-08-29 | v022 guarded off the network table — its "+" posted to the trainer's route, which production does not mount | static suite; the online funds dialog is untouched |
| 2026-08-29 | v028 + v029 + v030 merged into `v028-ready-phase.js` (3 files → 1, 3 requests → 1) | 321 static + 13 browser cases |
| 2026-08-29 | v039's `.felt::before` and `.table-glow` removed — the last two declarations in its two-class block that lost, and so the last that a load-order change could have woken | 321 static + 9 browser cases. Note: the first attempt replaced both rules as one string, which does not occur in the file (the `::after` line sits between them); the script reported success having changed nothing, and the green suites were green on an unchanged file. Read the diff, not the script's own word |
| 2026-08-29 | v039's dead frame properties removed (padding, overflow, box-shadow) — absolute values, all three losing to v038, all three would wake on a load-order change | 321 static + 9 browser cases, before the commit |
| 2026-08-29 | v039's dead felt paint removed (gradient, neon border, inset shadow). Its width/height/inset stay: the height is load-bearing, see the percentages warning above | 321 static + 9 browser cases, run **before** the commit this time |
| 2026-08-29 | **Reverted the same day (9f88bc5):** a first attempt also deleted the felt's height and the frame's padding/overflow/box-shadow. The net caught it at 6 of 9 -- "the felt ends 23px below the bottom edge" -- but the commit had already shipped, because the deploy was chained after a `pytest ... | tail` whose exit code is the tail's. Test, read the result, *then* commit | the net, on the way back |
| 2026-08-29 | v039's seven-point seat ring removed — the first of its dead two-class geometry; v040 has placed every seat for far longer, and holding the ring meant any load-order change moved the table | 321 static + 13 browser cases; the invariant moved to a test that reads v040 |
| 2026-08-29 | v035 and v036 deleted — 369 lines nothing loaded; `test_v101_regressions` was asserting v036's loader for v037, which never ran, and now reads component-ui.js | 321 static |
| 2026-08-30 | An idle snapshot no longer promotes a departed viewer from the last hand's stale roster. That split the UI exactly in two: the header hid "Занять место" as seated, while v040 followed `current_seats`, drew "Сесть", and its confirmation returned early on the same false seated state | 597 static + 9 browser-net cases + the mid-hand seat-claim browser case |
| 2026-08-30 | The mobile "Сесть" chair now carries `data-visual-seat="0"`, so it inherits the exact final hero anchor (`100% - 86px`) instead of v040's generic `80%`. Its circle and label also share the hero avatar's CSS variables; spectator → seated replaces the control in place instead of jumping about 75px plus the old 11px inner offset | 597 static + 9 browser-net cases + browser transitions at 360×800 and 402×874 + the mid-hand seat-claim case |
| 2026-08-30 | Removed the obsolete online centre card "МЕСТО ЗАНЯТО": the network table now keeps the local trainer's room prompt hidden in every online state, and online ready-up no longer binds that removed card as a click target | 597 static + online prompt regressions + 9 browser-net cases |
| 2026-08-30 | The mobile "УРАВНЯТЬ / СТАВКА" strip now follows the pot's existing `p8-no-pot` state instead of remaining on the felt between hands; the shared hide rule is deliberately after the strip's `on-felt` display rule so the cascade cannot paint it back in | 599 static + 10 browser cases, including the active-to-idle transition |
| 2026-08-30 | Desktop actions no longer own a separate 214px layout row. The existing panel is hosted by `.table-frame` and reuses the phone's four compact edge actions plus its transient sizing flow in the two free lower side zones; observer, acting-player and sizing transitions therefore leave the table box unchanged | 599 static + 11 action browser cases + 9 viewport safety-net cases; the two excluded mobile arc failures reproduce identically at `bf1f1f0` |
| 2026-08-30 | Fixed the returning Micro A role split: REST adds `viewer_seat_no`, WebSocket does not, and between hands v040's `game` is null. The socket render therefore lost the hero despite a valid `tableData.viewer_player_id`. v040 now resolves that id against the existing `tableData.seats` before choosing the watching ring; it does not retain a stale seat or trust a null id. Preserved the parallel transport normalization from `5bcaa12` | New regression failed in all 4 combinations (phone/desktop, with/without a past-hand roster), then passed including genuine spectator transitions; merged version: 603 static + 24 browser cases, with the same known mobile arc cases excluded |
| 2026-08-30 | Moved the desktop "Место забронировано" live region from the felt into the gap between table identity and header actions. The same node returns to the felt at phone width, where its existing hidden state remains unchanged. No duplicate status or queue controller | Browser regression failed with parent `felt`, then passed at 1485/1192/781px and on return to 390px; screenshot checked; 605 static + 29 browser cases passed, with the same 2 pre-existing mobile arc failures |
| 2026-08-30 | Unified desktop hero, board and hidden card sizes using one 66×92 base. Seat cards compensate for the centre cluster's existing 0.94 scale, so painted edge lengths match instead of just CSS widths. Removed the competing hero/back dimensions, retained fans and back-card layering, and raised the hero pair to clear the avatar's stake | Regression failed at 781/1192/1920px, then passed for all 17 cards at each width; screenshot and 9 viewport cases checked; final run: 607 static + 28 selected browser cases passed (known mobile arc cases excluded) |
| 2026-08-30 | Recoloured the shared phone/desktop back to graphite (#071A1A/#0B2020), muted turquoise pattern (#16CFA0 at 22%) and a thin #35F0C0 rim with 18% glow. Kept the mobile ring/diagonals and all card dimensions; idle decoration shares the same paint. Face-up exclusions use `:where` so hidden hero cards cannot inherit cyan paint and red/gold face-up accents retain their priority. Cache: desktop-oval-39 | Palette and face-up-priority regressions failed before their fixes, then passed at 390/1192px with visible/hidden hero cards; screenshots checked. Final: 35 browser cases and 610 non-browser tests passed, 1 skipped. The unchanged upstream `test_the_countdown_runs_out_instead_of_starting_over` fails because b80d782 removed `countdownText`; it was excluded from the final non-browser run. Independent review's specificity finding fixed and covered |
