from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TABLE = (ROOT / "static" / "v038-poker8-v2-cinematic-table.js").read_text(encoding="utf-8")
ONLINE = (ROOT / "static" / "online-table.js").read_text(encoding="utf-8")


def test_mobile_arc_reserves_half_a_hud_at_each_viewport_edge():
    assert "--p8-seat-safe-inset:50px" in TABLE
    assert "--p8-arc-radius:min(46vw,calc(50vw - var(--p8-seat-safe-inset)))" in TABLE


def test_header_utility_group_owns_the_right_edge():
    assert ".poker8-online .mobile-header-utility{order:2}" in ONLINE
    assert ".poker8-online .mobile-header-utility{margin-left:auto!important}" in ONLINE
    assert ".mobile-header-utility{margin-left:auto!important;}" in TABLE
    assert ".mobile-chat-button{margin-left:auto!important}" not in TABLE


def test_queued_seat_status_is_static_and_quiet():
    queued_start = ONLINE.index(
        ".poker8-online .mobile-header-seat-actions button.mode-active{"
    )
    queued_end = ONLINE.index("/* v037 built the chat/hint pair", queued_start)
    queued_rules = ONLINE[queued_start:queued_end]

    assert "p8HeaderGlowSpin" not in queued_rules
    assert "conic-gradient(from var(--glow-angle)" not in queued_rules
    assert "width:6px;height:6px;border-radius:50%;background:#55f3a8" in queued_rules


def test_mobile_center_stack_is_chips_then_pot_then_summary_then_board():
    """The call/bet strip moved up between the pot and the board.

    It used to sit under the board in the action panel, repeating the pot's
    own number. Asserted as an order rather than four literals so raising the
    pot -- which is what made room for the strip -- does not have to be
    re-typed here every time it moves.
    """
    import re

    def top_of(selector):
        # Several rules set each of these; the last one in the file is the one
        # that actually paints, since they tie on specificity.
        hits = re.findall(re.escape(selector) + r"\{top:(\d+)%!important;", TABLE)
        assert hits, selector
        return int(hits[-1])

    chips, pot, board = top_of(".pot-chips"), top_of(".pot-total"), top_of(".board-cards")

    summary = re.search(
        r"\.v038-hud-summary\.on-felt\{[^}]*?top:var\(--v038-summary-top,(\d+)%\)!important",
        TABLE,
        re.S,
    )
    assert summary, "the felt strip lost its position"
    strip = int(summary.group(1))

    assert chips < pot < strip < board, (chips, pot, strip, board)
    assert "(potRect.bottom + boardRect.top - summaryRect.height) / 2 - hostRect.top" in TABLE
    assert 'window.addEventListener("resize", queueSync)' in TABLE
    # It needs its own plate, or it reads as text lying loose on the felt.
    plate = TABLE[TABLE.index(".v038-hud-summary.on-felt{"):]
    plate = plate[:plate.index("}")]
    assert "background:" in plate and "border:" in plate
    assert "bottom:calc(183px + env(safe-area-inset-bottom))!important" in TABLE


def test_mobile_dealer_uses_the_side_opposite_the_timer_badge():
    """Opposite side, and now at the same height as the badge it mirrors.

    It sat at bottom:2px, level with the name plate, where it read as
    decoration on the name rather than as this player's button. The timer
    hangs off the avatar's right edge at calc(100% - 4px) -- 4px of overlap,
    vertically centred -- so the dealer takes the mirror of exactly that on
    the left. Measured live: 4px of overlap, dead centre on the avatar, clear
    of the plate.
    """
    rule = TABLE[TABLE.index(".dealer-button{left:"):]
    rule = rule[:rule.index("}")]
    assert "right:auto!important" in rule, "must stay on the left, opposite the timer"
    assert "bottom:auto!important" in rule, "no longer pinned to the plate"
    # The avatar is 44px tall from the seat's top, so a 22px badge centres at 11.
    assert "top:11px!important" in rule
    # The timer bites 4px into the avatar's right edge; this is its mirror.
    assert "left:-6px!important" in rule
    assert "left:calc(100% - 4px)" in TABLE, "the badge this mirrors moved"
