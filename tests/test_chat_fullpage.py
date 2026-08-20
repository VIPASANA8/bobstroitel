"""An open chat takes the page, and never costs the player a hand."""

from pathlib import Path

ONLINE = Path("static/online-table.js").read_text(encoding="utf-8")


def _block(selector):
    start = ONLINE.index(selector)
    return ONLINE[start:ONLINE.index("}", start)]


def test_the_open_chat_covers_the_page():
    """A 200px strip over the felt was too small to read a conversation in and
    too big to ignore."""
    rules = _block(".poker8-online .online-chat-panel.is-open{")
    assert "inset:0" in rules
    assert "display:flex!important" in rules and "flex-direction:column" in rules
    # The base rule carries align-self:start from when this was a card in a
    # grid, and that makes a fixed box shrink to its content rather than honour
    # top:0 and bottom:0 -- measured at 375x215 in an 812px viewport.
    assert "height:100dvh" in rules and "align-self:stretch" in rules
    # The feed scrolls; the composer stays put.
    feed = _block(".poker8-online .online-chat-panel.is-open #chatMessages{")
    assert "overflow-y:auto" in feed and "flex:1 1 auto" in feed
    # The docked panel capped the feed at 240px, which survived into this one
    # and left 440px of empty panel under the composer.
    assert "max-height:none" in feed


def test_the_turn_banner_only_appears_on_your_own_turn():
    body = ONLINE[ONLINE.index("function chatTurnSecondsLeft()"):]
    body = body[:body.index("\n  }")]
    assert 'state.phase !== "active"' in body
    assert "state.acting_player !== state.viewer_player_id" in body
    assert "state.action_deadline" in body


def test_the_count_is_refreshed_every_second():
    """A snapshot arrives when something happens; a clock has to move anyway."""
    body = ONLINE[ONLINE.index("function syncChatTurnBanner()"):]
    body = body[:body.index("\n  }\n")]
    assert "setInterval(syncChatTurnBanner, 1000)" in body
    assert "clearInterval(chatTurnTicker)" in body, "and stops when the turn passes"


def test_there_are_three_ways_back_to_the_table():
    """Missing a hand because you were reading is the one thing a full-page
    chat must not cause."""
    assert '.chat-turn-banner, .chat-close' in ONLINE, "the banner itself and the cross"
    assert 'event.key === "Escape"' in ONLINE


def test_the_banner_grows_urgent_before_the_clock_runs_out():
    body = ONLINE[ONLINE.index("function syncChatTurnBanner()"):]
    body = body[:body.index("\n  }\n")]
    assert "seconds <= 10" in body
    assert "prefers-reduced-motion" in ONLINE, "and holds still for anyone who asked"
