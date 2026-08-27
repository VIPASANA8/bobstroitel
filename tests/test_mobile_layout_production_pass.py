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


def test_mobile_center_stack_is_chips_then_pot_then_board_then_summary():
    assert ".pot-chips{top:29%!important;" in TABLE
    assert ".pot-total{top:38%!important;}" in TABLE
    assert ".board-cards{top:47%!important;}" in TABLE
    assert "bottom:calc(183px + env(safe-area-inset-bottom))!important" in TABLE


def test_mobile_dealer_uses_the_side_opposite_the_timer_badge():
    assert (
        ".dealer-button{left:-9px!important;right:auto!important;"
        "bottom:2px!important;width:22px!important;height:22px!important;}"
    ) in TABLE
