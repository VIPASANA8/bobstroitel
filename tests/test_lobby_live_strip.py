"""Variant B: a live pulse of real activity (players/tables) between the
entry CTAs and the table list, plus a stake tier (colour, glow, seat dots)
on each card -- built on top of the existing CTAs and card buttons, not in
place of them."""

import json
import subprocess
import tempfile
from pathlib import Path

LOBBY_HTML = Path("static/lobby.html").read_text(encoding="utf-8")
LOBBY_JS = Path("static/lobby.js").read_text(encoding="utf-8")
NETWORK_CSS = Path("static/network.css").read_text(encoding="utf-8")


def test_the_two_entry_ctas_have_no_description_text():
    ctas = LOBBY_HTML[LOBBY_HTML.index('class="lobby-ctas"'):LOBBY_HTML.index('id="activeSession"')]
    assert "<small>" not in ctas
    assert "Быстрая игра" in ctas and "Создать комнату" in ctas


def test_the_two_ctas_stay_side_by_side_even_on_a_narrow_phone():
    """.lobby-ctas used to collapse to one column under 640px -- the button
    pair now has to fit one row at every width the description text used to
    justify wrapping under."""
    narrow = NETWORK_CSS[NETWORK_CSS.index("@media (max-width:640px)"):]
    narrow = narrow[:narrow.index("}\n") + 2]
    assert "grid-template-columns:1fr" not in narrow
    assert "grid-template-columns:repeat(2" in NETWORK_CSS


def test_seat_dots_stay_a_compact_row_on_a_narrow_card():
    """The pre-existing @media(max-width:760px) rule set every .card-bottom
    span to display:block -- written for two lines of text ("Бай-ин ..."
    over "4 / 6"). Measured live on a real card at 375px: the six 6px seat
    dots stretched to the card's full 321px width instead of staying an
    ~50px row. Same specificity as that old rule, so this only wins by
    coming later in the file -- must actually be after it, not just present."""
    media_start = NETWORK_CSS.index("@media(max-width:760px)")
    media_span = NETWORK_CSS[media_start:media_start + NETWORK_CSS[media_start:].index("}}") + 2]
    assert ".card-bottom span{display:block}" in media_span, "the old rule this works around moved or was rephrased"
    fix_pos = NETWORK_CSS.index(".card-bottom span{display:inline-flex")
    assert fix_pos > media_start + len(media_span), "the override must come after the media block to win"


def test_the_felt_strip_sits_between_the_ctas_and_the_table_heading():
    ctas_end = LOBBY_HTML.index("</section>", LOBBY_HTML.index('class="lobby-control"'))
    heading_start = LOBBY_HTML.index('class="section-heading"')
    between = LOBBY_HTML[ctas_end:heading_start]
    assert 'class="felt-strip"' in between
    assert 'id="liveHeadline"' in between
    assert 'id="liveSub"' in between


def test_both_original_ctas_are_still_there():
    """The mockup this shipped from only carried a single "Быстрый вход"
    button in the felt strip -- дropping "Создать комнату" entirely. Both
    entry points from before stay, the felt strip is additional."""
    assert 'id="quickPlay"' in LOBBY_HTML
    assert 'id="createRoom"' in LOBBY_HTML


def _extract(start_marker, end_marker):
    start = LOBBY_JS.index(start_marker)
    end = LOBBY_JS.index(end_marker, start)
    return LOBBY_JS[start:end]


def test_the_functions_are_still_there_to_extract():
    assert "const tierFor = table =>" in LOBBY_JS
    assert "function pluralRu" in LOBBY_JS
    assert "function renderLiveStrip" in LOBBY_JS


def _run_tier(big_blind_units):
    block = _extract("const TIER_GLOW", "\n  };\n") + "\n  };"  # tierFor's own closing brace
    harness = block + f"\nconsole.log(tierFor({{big_blind_units:{json.dumps(big_blind_units)}}}));"
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
        handle.write(harness)
        path = handle.name
    result = subprocess.run(["node", path], capture_output=True, text=True, encoding="utf-8", check=True)
    return result.stdout.strip()


def test_tier_buckets_on_the_blind_size_not_the_table_name():
    """A player-created room's blinds (from /api/lobby/room-levels) still
    need a real tier -- bucketed by size, not by matching "Micro"/"Low"/"Mid"
    against the table name, which a custom room's own name never contains."""
    assert _run_tier(100) == "micro"
    assert _run_tier(200) == "low"
    assert _run_tier(1000) == "mid"
    assert _run_tier(150) == "low", "between micro and low -- rounds up to the safer (lower) tier label"
    assert _run_tier(5000) == "mid"


def _run_plural(n):
    block = _extract("function pluralRu", "\n  }\n") + "\n  }"
    harness = block + f'\nconsole.log(pluralRu({n}, "игрок", "игрока", "игроков"));'
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
        handle.write(harness)
        path = handle.name
    result = subprocess.run(["node", path], capture_output=True, text=True, encoding="utf-8", check=True)
    return result.stdout.strip()


def test_russian_pluralization_handles_the_11_to_14_exception():
    """The naive mod-10 rule alone gets 11-14 wrong (11 % 10 == 1 would say
    "игрок", but it is "11 игроков") -- mod-100 has to be checked first."""
    assert _run_plural(1) == "игрок"
    assert _run_plural(21) == "игрок"
    assert _run_plural(2) == "игрока"
    assert _run_plural(4) == "игрока"
    assert _run_plural(5) == "игроков"
    assert _run_plural(11) == "игроков"
    assert _run_plural(14) == "игроков"
    assert _run_plural(0) == "игроков"


def _run_live_strip(occupied_counts):
    tier_block = _extract("const TIER_GLOW", "\n  };\n") + "\n  };"
    plural_block = _extract("function pluralRu", "\n  }\n") + "\n  }"
    strip_block = _extract("function renderLiveStrip", "\n  }\n") + "\n  }"
    tables = json.dumps([{"occupied_count": n} for n in occupied_counts])
    harness = f"""
    let tables = {tables};
    const targets = {{}};
    function $(id) {{ targets[id] = targets[id] || {{}}; return targets[id]; }}
    {tier_block}
    {plural_block}
    {strip_block}
    renderLiveStrip();
    console.log(JSON.stringify({{ headline: targets.liveHeadline.textContent, sub: targets.liveSub.textContent }}));
    """
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
        handle.write(harness)
        path = handle.name
    result = subprocess.run(["node", path], capture_output=True, text=True, encoding="utf-8", check=True)
    return json.loads(result.stdout)


def test_the_strip_sums_real_occupancy_not_a_guess():
    result = _run_live_strip([4, 5, 0, 6])
    assert result == {"headline": "15 игроков сейчас", "sub": "за 3 активными столами"}


def test_an_empty_lobby_invites_instead_of_reporting_zero_flatly():
    result = _run_live_strip([0, 0, 0])
    assert result["headline"] == "0 игроков сейчас"
    assert result["sub"] == "столы свободны — начните первым"


def test_the_table_card_gains_tier_and_seats_and_a_lock_for_password_rooms():
    """The card's own seat-vs-buy-in decision moved onto the table page
    itself (its "Занять место" header button, already built) -- one "Войти"
    now opens the table exactly like the eye icon used to, so there is only
    ever one way in from a card. Copying a link is gone entirely -- a
    password protects the seat instead -- so the only owner-only control
    left on a card is closing the room."""
    body = _extract("function renderTables()", "document.querySelectorAll(\"[data-observe-table]\")")
    assert 'class="tier-tag' in body
    assert 'class="seats' in body
    assert "data-table=" not in body, "the buy-in-dialog path was retired from the card"
    assert "data-copy-room" not in body
    assert ">Войти<" in body
    assert "→" not in body, "no arrow on the entry button"
    assert 'data-observe-table="${escape(table.id)}"' in body
    assert 'data-close-room="${escape(table.id)}"' in body
    assert "table.has_password" in body
    assert 'data-close-room="${escape(table.id)}"' in body


def test_quick_play_still_uses_the_buy_in_dialog_with_a_chosen_amount():
    """Only the per-card button changed -- Quick Play still lets the player
    pick a buy-in amount, since it hands you a specific table you did not
    already choose to just look at."""
    handler = LOBBY_JS[LOBBY_JS.index('$("quickPlay")'):][:250]
    assert "openBuyIn(" in handler
