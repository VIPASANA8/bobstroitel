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


def test_the_acting_avatar_is_ringed_in_white():
    """White carries no meaning of its own, which is why it can sit on top of
    six different seat hues at full strength without arguing with any of them.

    The plate under it and the timer keep the turn colour: the ring is the
    spotlight, the magenta is the label.
    """
    for source in (TABLE, TURN):
        rule = source[source.index(".player-avatar{", source.index("active-turn .player-avatar{")
                                   if "active-turn .player-avatar{" in source
                                   else source.index("p8-turn-gradient .player-avatar{")):]
        rule = rule[:rule.index("}")]
        assert "border-color:var(--turn-ring)!important" in rule, rule[:90]
        assert "var(--turn)," not in rule


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


def test_arming_a_press_survives_its_own_click():
    """A document listener cancelled any armed action on a click outside
    [data-v038-all-in-trigger] -- an attribute nothing sets. So the button's
    own click bubbled up and disarmed what it had just armed, and fold and
    all-in both did nothing at all."""
    assert 'closest?.("[data-action-key],[data-v038-all-in-trigger]")' in TABLE
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
