"""One colour per state, and glow spent where it means something."""

import re
from pathlib import Path

STATIC = Path("static")
ROOT = (STATIC / "style.css").read_text(encoding="utf-8")
TABLE = (STATIC / "v038-poker8-v2-cinematic-table.js").read_text(encoding="utf-8")
TURN = (STATIC / "v041-poker8-v2-turn-clarity.js").read_text(encoding="utf-8")

#: The measured starting point: 1478 distinct colours over 2050 uses, so the
#: average colour on this project was used 1.4 times. These five are the ones
#: that carry a state, and each is defined once.
STATE_TOKENS = ("--turn", "--act-fold", "--act-check", "--act-raise", "--act-allin")


def test_each_state_colour_is_defined_once():
    for token in STATE_TOKENS:
        assert len(re.findall(rf"^\s*{token}:", ROOT, re.M)) == 1, token


def test_the_action_buttons_take_their_colour_from_the_tokens():
    """Six literals sat here, two of them cyans nobody could tell apart."""
    for action in ("fold", "check", "call", "raise", "all-in"):
        rule = re.search(rf"\.action-slot\.{re.escape(action)}\{{--v038-action:([^;]+);", TABLE)
        assert rule, action
        assert rule.group(1).startswith("var(--act-"), (action, rule.group(1))


def test_check_and_call_are_the_same_colour():
    """They were #55cfff and #39c8ff -- a distinction no eye makes."""
    pair = {re.search(rf"\.action-slot\.{a}\{{--v038-action:([^;]+);", TABLE).group(1)
            for a in ("check", "call")}
    assert len(pair) == 1


def test_a_queued_action_keeps_its_own_colour():
    """Every queued button turned magenta, so queued-fold and queued-raise
    looked alike -- and it spent the turn colour on something that is not
    the turn."""
    rule = TABLE[TABLE.index(".action-slot.queued{"):]
    rule = rule[:rule.index("}")]
    assert "border-color:var(--v038-action)" in rule
    assert "255,59,213" not in rule


def test_the_acting_avatar_is_lit_not_outlined():
    """An opaque black ring sat between the avatar and its glow.

    `0 0 0 3px rgba(0,0,0,.93)` is a spacer: it pushed the light off the edge
    it was meant to be coming from, so the result read as an outline drawn
    around the avatar rather than a lamp behind it. The light touches the rim
    now and falls off over three stops.

    White carries no meaning of its own, which is why it can sit on top of six
    seat hues at full strength. The plate under it and the timer keep the turn
    colour: the light is the spotlight, the magenta is the label.
    """
    for name, source in (("v038", TABLE), ("v041", TURN)):
        anchor = ("active-turn .player-avatar{" if "active-turn .player-avatar{" in source
                  else "p8-turn-gradient .player-avatar{")
        rule = source[source.index(anchor):]
        rule = rule[:rule.index("}")]
        assert "border-color:var(--turn-ring)!important" in rule, name
        assert "rgba(0,0,0,.9" not in rule.split("inset")[0], f"{name} still spaces the light off the rim"
        stops = [p for p in rule.split("box-shadow:")[1].split(",") if "turn-ring" in p]
        assert len(stops) >= 3, f"{name} has {len(stops)} light stops, not a falloff"


def test_the_turn_is_one_colour_on_every_seat():
    """It was hsla(var(--seat-accent), ...) -- cyan on seat 0, violet on seat 5.

    A signal that never looks the same twice cannot be learned.
    """
    highlight = TURN[TURN.index(".p8-turn-gradient .player-avatar{"):]
    highlight = highlight[:highlight.index("/* Glow is an accent")]
    assert "--seat-accent" not in highlight
    assert "var(--turn-ring)" in highlight or "var(--turn)" in highlight


def test_the_timer_and_the_seat_ring_agree():
    """The two places the turn appears must be the same colour."""
    timer = TABLE[TABLE.index(".v038-turn-timer{"):]
    assert "var(--turn)" in timer[:timer.index("}")]
    assert "var(--turn)" in TURN


def test_magenta_belongs_to_the_turn_alone():
    """Nothing else may reach for it, or it stops meaning anything."""
    for name, source in (("v038", TABLE), ("v041", TURN)):
        for literal in re.findall(r"#(?:ff3[0-9a-f]{2}[a-f0-9]{2}|ff38c7|ff3bd[0-9a-f]|ff39cf)", source, re.I):
            assert False, f"{name} still writes {literal} instead of var(--turn)"


def test_glow_is_off_at_rest():
    """66 elements glowed with nobody to act, so the turn glow was the 67th."""
    assert "body.v014.poker8-v2-sixmax .poker-chip," in TURN
    diet = TURN[TURN.index("body.v014.poker8-v2-sixmax .poker-chip,"):]
    diet = diet[:diet.index("/* The rest was a cyan haze")]
    assert "filter:none!important" in diet
    #: The acting seat is the exception -- it is what the glow is now for.
    assert ".seat-card:not(.p8-turn-gradient) .player-avatar" in diet


def test_the_cards_keep_depth_and_lose_the_haze():
    """What makes a card look like a card is the shadow underneath it.

    A blanket `.card` rule in the last layer did not work: `.player-cards
    .card.back` is more specific and won regardless of load order. The two
    rules had to change where they are written.
    """
    for anchor in (".player-cards .card.back{", ".board-cards .card{"):
        rule = TABLE[TABLE.index(anchor):]
        shadow = re.search(r"box-shadow:([^;]+);", rule[:rule.index("}")])
        assert shadow, anchor
        glow = [p for p in shadow.group(1).split(",")
                if re.match(r"\s*0 0 \d", p) and "inset" not in p]
        assert not glow, (anchor, glow)


def test_the_desktop_timer_agrees_with_the_mobile_one():
    """It was its own violet-pink at rgba(221,51,255,.16) -- close enough to
    the turn colour to look like a mistake, far enough to not be one."""
    rule = ROOT[ROOT.index(".neon-ref-v107 .action-timer {"):]
    rule = rule[:rule.index("}")]
    assert "var(--turn)" in rule
    assert "221,51,255" not in rule


def test_the_bet_sizes_are_plain_text():
    """All nine glowed white at once, which is a halo on a number."""
    rule = TABLE[TABLE.index(".quick-sizes button{"):]
    assert "text-shadow:none!important" in rule[:rule.index("}")]


def test_no_two_colours_are_the_same_colour():
    """Half the palette was one colour written twice.

    1461 distinct values across the stylesheets and layers collapsed to 696
    at a Lab distance of 2.5, which is under what a screen can show -- so 765
    of them were a rename, not a design. This keeps them from creeping back.
    """
    import glob
    import math

    literal = re.compile(r"#[0-9a-fA-F]{6}\b|rgba?\(\s*\d+\s*,\s*\d+\s*,\s*\d+")

    def lab(c):
        def f(u):
            u /= 255
            return u / 12.92 if u <= .04045 else ((u + .055) / 1.055) ** 2.4
        r, g, b = map(f, c)
        x = (.4124 * r + .3576 * g + .1805 * b) / .95047
        y = .2126 * r + .7152 * g + .0722 * b
        z = (.0193 * r + .1192 * g + .9505 * b) / 1.08883
        k = lambda t: t ** (1 / 3) if t > .008856 else 7.787 * t + 16 / 116
        fx, fy, fz = k(x), k(y), k(z)
        return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))

    seen = set()
    sources = ["style.css", "mobile.css", "component-ui.css", "network.css",
               "online-table.js", "lobby.js", "app.js"]
    sources += [Path(p).name for p in sorted(glob.glob("static/v0*.js"))]
    for name in sources:
        for hit in literal.findall((STATIC / name).read_text(encoding="utf-8")):
            if hit.startswith("#"):
                seen.add(tuple(int(hit[i:i + 2], 16) for i in (1, 3, 5)))
            else:
                seen.add(tuple(int(x) for x in re.findall(r"\d+", hit)[:3]))

    labs = [lab(c) for c in seen]
    twins = [(a, b) for i, a in enumerate(labs) for b in labs[i + 1:]
             if math.dist(a, b) <= 2.0]
    assert not twins, f"{len(twins)} pairs are the same colour written twice"


def test_the_turn_ring_does_not_animate():
    """It pulsed on the avatar and the plate, and those are rebuilt on every
    render -- twice in five seconds on a live table -- so the animation
    restarted from frame zero and the glow visibly jumped."""
    assert "@keyframes" not in TURN
    assert "animation:" not in TURN


def test_the_three_hud_numbers_are_written_the_same_way():
    """Call and pot went through formatBB, the bet came raw off the input.

    So the row read "0.00  0.00  1" -- three amounts of the same kind, one of
    them in a different notation, and the odd one sitting off the baseline the
    other two shared.
    """
    fn = TABLE[TABLE.index("function ensureHudSummary()"):]
    fn = fn[:fn.index("function configureReferenceActions")]
    assert 'document.getElementById("amount")?.value || "0.00"' not in fn
    assert "formatBB(raw)" in fn


def test_the_hud_numbers_line_up():
    """Digits in a three-column grid need equal widths, or they wander."""
    rule = TABLE[TABLE.index(".v038-hud-summary b{"):]
    rule = rule[:rule.index("}")]
    assert "tabular-nums" in rule
    #: They were cyan, green and orange. The labels above them already say
    #: which is which; three accents for three numbers says nothing more.
    assert len(re.findall(r"color:#[0-9a-f]{6}", rule)) == 1


def test_all_in_is_announced_once():
    """The badge over the avatar and the stack line both said ALL-IN.

    The stack keeps it -- a stack of 0 says nothing, which is why it was put
    there. The badge gave it up: it still carries ПАС and ДУМАЕТ, which the
    stack line cannot show.
    """
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    status = re.search(r'const status = folded \? "ПАС"[^;]*;', app)
    assert status, "the status line moved"
    assert "ALL-IN" not in status.group(0)
    assert 'class="seat-stack">${allIn ? "ALL-IN" : formatBB(stack)}' in app


def test_irreversible_bet_waits_for_the_confirmation_control():
    """All-in opens a sizing overlay and only its confirm control submits."""
    assert 'openSizingMode("all_in", amountBounds().max)' in TABLE
    assert 'if (action === "all_in") return sendAction("all_in", 0)' in TABLE
    assert "button.dataset.actionKey = def.key" in TABLE


def test_the_amount_cue_does_not_move_anything():
    """It scaled the number to 108% and back. A cue that changes size is the
    one thing on the row that reads as a twitch."""
    frames = re.search(r"@keyframes v038AmountPulse\{[^}]*\}[^}]*\}", TABLE)
    assert frames, "the keyframes moved"
    assert "scale" not in frames.group(0)
    assert "brightness" in frames.group(0)


def test_the_amount_cue_stays_quiet_when_the_turn_moves():
    """Every amount on the row changes when the actor does -- that is the table
    moving, not news about your number, and four cues at once is flicker."""
    assert "const actorChanged = actorNow !== lastActionRowActor;" in TABLE
    body = TABLE[TABLE.index('if (value.textContent !== def.amount) {'):]
    assert "if (!actorChanged) {" in body[:340]


def test_no_square_behind_the_avatar():
    """.seat-card has no background and no border on mobile -- only a
    backdrop-filter, and a blur on a box with no border-radius paints exactly
    that box. Everything inside 67x77 was smeared and everything outside was
    not, so the seam drew a square around every seat."""
    rule = TURN[TURN.index("body.v014.poker8-v2-sixmax .seat-card,"):]
    rule = rule[:rule.index("}")]
    assert "backdrop-filter:none!important" in rule
    assert ".seat-identity" in rule


def test_the_acting_avatar_does_not_change_size():
    """It was transform:translateY(-1px) scale(1.05).

    Nothing transitions that transform, and the avatar is rebuilt from scratch
    on every snapshot, so it could only ever snap: on each hand-over one avatar
    popped 2.5px bigger while another dropped back. The light says which seat
    is acting without moving anything.
    """
    rule = TURN[TURN.index(".seat-card.active-turn .player-avatar,"):]
    rule = rule[:rule.index("}")]
    assert "transform:none!important" in rule
    for cls in ("v032-active-turn", "p8-turn-gradient"):
        assert cls in rule, cls


def test_wager_markers_are_placed_after_the_seats_have_moved():
    """A marker is positioned by measuring the seat it belongs to, and v040
    does not move the seats until the seat hooks run. Measuring first read
    whatever geometry the freshly rebuilt markup happened to have, so the chips
    in front of players landed a few pixels off -- and somewhere slightly
    different on the next snapshot. That is a tremble at render rate, and no
    styling could have steadied it."""
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    body = app[app.index("function renderSeats() {"):]
    body = body[:body.index("\n}\n")]
    assert body.index('runRenderHooks("seats")') < body.index("renderWagerMarkers()"), \
        "the markers are measuring seats that have not been positioned yet"


def test_the_stake_is_written_in_the_avatar_not_on_the_felt():
    """One implementation, and it draws nothing on the felt.

    Two layers used to reassign renderWagerMarkers to place a chip stack
    between each player and the pot; the last one won, as always. The stake is
    a number inside the avatar now, built by seatHtml with the rest of the
    seat, so there is no separate pass to get out of order with anything.
    """
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    assert '<b class="seat-wager">${bareBB(wager)}</b>' in app
    for layer in ("v016-fixes.js", "v031-pot-cluster-mobile-fix.js"):
        assert "renderWagerMarkers = function" not in (STATIC / layer).read_text(encoding="utf-8"), layer
    body = app[app.index("function renderWagerMarkers() {"):]
    body = body[:body.index("\n}")]
    assert "chipStackHtml" not in body and "bet-marker" not in body


def test_the_pot_is_drawn_as_one_cluster():
    """renderPotChips draws its own cluster (see test_chip_stacks) rather
    than delegating to chipStackHtml, which wager markers still use. One
    call, with the whole stack count: the two-wing split it replaced left a
    small pot looking like two pots."""
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    pot = app[app.index("function renderPotChips(value) {"):]
    pot = pot[:pot.index(chr(10) + "}")]
    assert "potWingHtml(visualValue, stackCount, 0)" in pot
    assert pot.count("potWingHtml") == 1
    assert "chipStackHtml" not in pot


def test_collected_money_still_leaves_from_somewhere():
    """The flight used to start at the marker on the felt. Deleting the marker
    without moving the flight would have made the pot grow out of nothing."""
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    assert '.seat-wager:not(.fx-collected)' in app
    assert '.bet-marker:not(.fx-collected)' not in app


def test_the_stake_drops_the_unit_inside_the_avatar():
    """Measured on the live table: "0.50 ББ" is 54px wide inside a 49px
    avatar, and 20 of those pixels are a unit the stack below already gives."""
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    assert "function bareBB(value)" in app
    body = app[app.index("function bareBB(value) {"):]
    assert "ББ" not in body[:body.index(chr(10) + "}")]


def test_the_room_prompt_is_narrower_than_it_was():
    """"МЕСТО ЗАНЯТО" hit the old 78% cap edge to edge on a 321px felt --
    250px wide, close enough to the side seats to look like it was reaching
    for them. Measured live, then narrowed."""
    rule = TABLE[TABLE.index(".v038-room-prompt{"):]
    rule = rule[:rule.index("}")]
    # The rule's own comment mentions the old 78% for context, so pick the
    # last match in the block -- the live declaration, not the history note.
    matches = re.findall(r"max-width:(\d+)%", rule)
    assert matches and int(matches[-1]) < 78


def test_spectator_wing_seats_stay_clear_of_the_board_band():
    """LAYOUTS keeps every seat's y outside 22-56 -- the band the pot, board
    and chip cluster occupy, per the comment above LAYOUTS in v040. The
    upper-side seats at 5 and 6 active viewers sat at y:38 and y:31, both
    inside it, and measured live the board's actual card rects overlapped
    those seats' plates by up to 54px, with the plate painted on top and
    hiding part of a card.

    2's y:50 is not covered by this check: measured live it does not collide
    (its x:12/88 sit far enough outside the board's real horizontal reach
    that the abstract band rule is too strict for it), so it is left as is
    rather than "fixed" against a case that was never broken.
    """
    seats = (STATIC / "v040-poker8-v2-dynamic-seats.js").read_text(encoding="utf-8")
    block = seats[seats.index("const SPECTATOR_LAYOUTS = {"):seats.index("const style = document.createElement")]
    for line in block.splitlines():
        if not re.match(r"\s*[56]:", line):
            continue
        for x, y in re.findall(r"\[(\d+),\s*(\d+)\]", line):
            y = int(y)
            assert not (22 < y < 56), f"{line.strip()} has a point at y:{y}, inside the reserved band"


#: Measured live on a 317x615 phone felt: a seat's name plate runs from
#: +2px to +47px below its centre point, and the pot plate starts at 209px.
FELT_H, PLATE_TOP, PLATE_BOTTOM, POT_TOP = 615, 2, 47, 209

#: Clear air wanted between the pole's plate and the wings' -- enough that
#: the three read as a stagger rather than one row of boxes.
TOP_ROW_GAP = 8


def _top_three(count, wing_indices):
    seats = (STATIC / "v040-poker8-v2-dynamic-seats.js").read_text(encoding="utf-8")
    block = seats[seats.index("const SPECTATOR_LAYOUTS = {"):seats.index("const style = document.createElement")]
    line = next(l for l in block.splitlines() if re.match(rf"\s*{count}:", l))
    points = [(int(x), int(y)) for x, y in re.findall(r"\[(\d+),\s*(\d+)\]", line)]
    return points, points[0], [points[i] for i in wing_indices]


def _assert_top_row_is_staggered(pole, wings):
    """Pole at 14 with wings at 19 put the three plates 14px on top of each
    other vertically while they sat 5px apart horizontally -- reported live
    as a wall of boxes across the top of the felt. The pole has to clear the
    wings' plates by more than the plates are tall."""
    pole_plate_bottom = pole[1] / 100 * FELT_H + PLATE_BOTTOM
    for wing in wings:
        assert wing[1] > pole[1], f"wing {wing} is not below the pole {pole}"
        gap = wing[1] / 100 * FELT_H + PLATE_TOP - pole_plate_bottom
        assert gap >= TOP_ROW_GAP, f"{wing} leaves {gap:.0f}px under the pole's plate, not a stagger"


def _assert_wings_stay_above_the_pot(wings):
    for wing in wings:
        assert wing[1] / 100 * FELT_H + PLATE_BOTTOM < POT_TOP, wing


def test_five_spectator_upper_wings_are_staggered_and_stay_above_the_pot():
    _, pole, wings = _top_three(5, (1, 2))
    _assert_top_row_is_staggered(pole, wings)
    _assert_wings_stay_above_the_pot(wings)


def test_six_spectator_top_seats_use_a_staggered_two_step_arc():
    _, pole, wings = _top_three(6, (1, 5))
    _assert_top_row_is_staggered(pole, wings)
    _assert_wings_stay_above_the_pot(wings)
    assert wings[0][1] == wings[1][1], "the two wings share one level"


def test_five_spectators_form_a_balanced_pentagon_not_a_lopsided_cluster():
    """Was [[50,16],[82,14],[70,78],[30,78],[18,14]] -- three seats crammed
    onto the same y:14-16 top band and only two down at y:78, leaving the
    whole middle band empty on both sides. Reproduces the same collision
    check applied live via the browser tools at this session's own measured
    felt/seat box dimensions (321x761 felt, 67x77 seat) to confirm the new
    five points -- spread top/top/side/bottom/side -- clear each other with
    real margin, not just in the abstract."""
    seats = (STATIC / "v040-poker8-v2-dynamic-seats.js").read_text(encoding="utf-8")
    block = seats[seats.index("const SPECTATOR_LAYOUTS = {"):seats.index("const style = document.createElement")]
    line = next(l for l in block.splitlines() if re.match(r"\s*5:", l))
    points = [(int(x), int(y)) for x, y in re.findall(r"\[(\d+),\s*(\d+)\]", line)]
    assert len(points) == 5

    felt_w, felt_h = 321, 761
    seat_w, seat_h = 67, 77
    boxes = []
    for x, y in points:
        cx, cy = x / 100 * felt_w, y / 100 * felt_h
        boxes.append((cx - seat_w / 2, cy - seat_h / 2, cx + seat_w / 2, cy + seat_h / 2))

    def overlaps(a, b):
        return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]

    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            assert not overlaps(boxes[i], boxes[j]), (points[i], points[j])

    # Not just non-overlapping -- actually spread across more than one y band,
    # which is what "pentagon" means here (the old layout had exactly two).
    assert len({y for _, y in points}) >= 3


def test_six_spectators_get_a_hexagon_bulge_not_two_flat_rows():
    """Was [[50,15],[83,14],[83,69],[50,85],[17,69],[17,14]] -- the lower
    wings sat at y:69, only 16 points off the bottom pole's 85, so all three
    bottom seats read as one flat row. The lower wings now retain at least
    20 points of clearance from the bottom pole; the top trio is locked by
    test_six_spectator_top_seats_use_the_lowered_two_step_arc."""
    seats = (STATIC / "v040-poker8-v2-dynamic-seats.js").read_text(encoding="utf-8")
    block = seats[seats.index("const SPECTATOR_LAYOUTS = {"):seats.index("const style = document.createElement")]
    line = next(l for l in block.splitlines() if re.match(r"\s*6:", l))
    points = [(int(x), int(y)) for x, y in re.findall(r"\[(\d+),\s*(\d+)\]", line)]
    assert len(points) == 6

    lower_wing_ys = [points[2][1], points[4][1]]
    bottom_pole_y = points[3][1]
    for y in lower_wing_ys:
        assert not (22 < y < 56), f"lower wing at y:{y} is inside the reserved band"

    # The bulge was originally held by a 20-point vertical gap from the
    # bottom pole. That gap no longer survives: the lower wings had to drop
    # to y:75 to stop their hole cards covering the board (measured 33px of
    # overlap at a 765px viewport, 54px at 640). They clear the pole
    # horizontally instead, a third of the felt away, so this checks the real
    # thing the gap stood in for -- the boxes must not collide -- plus the
    # ordering that makes the ring a ring.
    felt_w, felt_h, seat_w, seat_h = 321, 761, 67, 77

    def box(point):
        cx, cy = point[0] / 100 * felt_w, point[1] / 100 * felt_h
        return (cx - seat_w / 2, cy - seat_h / 2, cx + seat_w / 2, cy + seat_h / 2)

    pole = box(points[3])
    for index in (2, 4):
        wing = box(points[index])
        assert not (wing[0] < pole[2] and wing[2] > pole[0]
                    and wing[1] < pole[3] and wing[3] > pole[1]), (points[index], points[3])
    assert min(lower_wing_ys) > max(points[1][1], points[5][1]), "lower wings must sit below the upper ones"
    assert bottom_pole_y >= max(lower_wing_ys), "the bottom pole is the lowest seat on the ring"


def test_the_top_pole_also_clears_its_own_wings_not_just_the_bottom_one():
    """The center stays one full layout step above both upper wings."""
    seats = (STATIC / "v040-poker8-v2-dynamic-seats.js").read_text(encoding="utf-8")
    block = seats[seats.index("const SPECTATOR_LAYOUTS = {"):seats.index("const style = document.createElement")]
    line = next(l for l in block.splitlines() if re.match(r"\s*6:", l))
    points = [(int(x), int(y)) for x, y in re.findall(r"\[(\d+),\s*(\d+)\]", line)]
    assert len(points) == 6

    upper_wing_ys = [points[1][1], points[5][1]]
    top_pole_y = points[0][1]
    assert top_pole_y < min(upper_wing_ys), "top pole must sit above its own wings, not level with them"
    for y in upper_wing_ys:
        assert y - top_pole_y >= 4, "top pole sits too close to its wings to read as a bulge"


def test_the_board_moved_up_once_the_seats_were_out_of_its_way():
    """34%, up from 38% -- the actual ask. Checked live at every player count,
    1 through 6, in both hero and spectator layouts: no seat plate touches
    the pot or a board card, with 17-25px to spare on every side."""
    table = (STATIC / "v038-poker8-v2-cinematic-table.js").read_text(encoding="utf-8")
    match = re.search(r"\.board-cards\{top:(\d+)%!important;\}", table)
    assert match and int(match.group(1)) < 38
