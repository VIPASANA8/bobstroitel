"""Both ways into a seat ask the same thing, and the hint lines its cards up.

Sitting from the felt used to skip the buy-in dialog entirely and buy in
for a flat 40 BB, while the header's "Занять место" opened the slider --
so the same chair cost a different stack depending on which control you
pressed.

The hand-rankings hint laid each row out on its own grid with an `auto`
card column, so a five-card hand pushed its name further right than a pair
did and the groups sat on no common axis.
"""

import re
from pathlib import Path

ONLINE = Path("static/online-table.js").read_text(encoding="utf-8")
V037 = Path("static/table-guide.js").read_text(encoding="utf-8")


def test_a_seat_on_the_felt_opens_the_buy_in_dialog():
    start = ONLINE.index('const button = event.target?.closest?.("[data-add-seat]");')
    handler = ONLINE[start:ONLINE.index("});", start)]
    assert "showBuyInDialog(Number(button.dataset.addSeat))" in handler
    assert "ready(Number(button.dataset.addSeat))" not in handler


def test_the_dialog_seats_the_chair_that_was_pressed():
    """The header has no particular chair in mind and stays null, so the
    server takes the first free one; a click on a seat means that seat."""
    assert "function showBuyInDialog(seatNo = null)" in ONLINE
    assert "pendingBuyInSeat = Number.isFinite(seatNo) ? seatNo : null;" in ONLINE
    assert "ready(pendingBuyInSeat, bb)" in ONLINE
    assert "ready(null, bb)" not in ONLINE


def test_every_hand_shows_its_cards_on_the_same_axis():
    row = V037[V037.index(".hand-rankings-modal .hr-row{"):]
    row = row[:row.index("}")]
    assert "grid-template-columns:20px var(--hr-cards-w) 1fr" in row
    assert "auto 1fr" not in row, "an auto column is per-row, so it cannot align rows"

    # Wide enough for the longest hand, or the five-card rows overflow it.
    width = int(re.search(r"--hr-cards-w:(\d+)px", V037).group(1))
    card = int(re.search(r"\.hr-card\{[^}]*width:(\d+)px", V037, re.S).group(1))
    overlap = int(re.search(r"\.hr-card\{[^}]*margin-left:-(\d+)px", V037, re.S).group(1))
    assert width == card + 4 * (card - overlap), (width, card, overlap)
    cards = V037[V037.index(".hand-rankings-modal .hr-cards{"):]
    assert "justify-content:center" in cards[:cards.index("}")]


def test_the_action_grid_keeps_one_arrangement_on_every_street():
    """ALL-IN | CHECK/CALL over FOLD | RAISE, whether or not there is a bet
    to call. The grid fills left to right and top to bottom, so the order of
    these definitions is the layout -- and a thumb that has learned where
    FOLD is should not have it move between streets. Leaving the hand is the
    left column, staying in it is the right."""
    table = Path("static/v038-poker8-v2-cinematic-table.js").read_text(encoding="utf-8")
    body = table[table.index("function mobileActionDefinitions("):]
    body = body[:body.index(chr(10) + "  }")]

    facing, free = body.split("return [", 1)[1], body.rsplit("return [", 1)[1]
    for arm, second in ((facing, "call"), (free, "check")):
        keys = re.findall(r'key:"([a-z_]+)"', arm)[:4]
        assert keys == ["all_in", second, "fold", "aggressive"], (second, keys)

    positions = dict(zip(re.findall(r'key:"([a-z_]+)"', free),
                         re.findall(r'edge:"(\w+)", slot:"(\w+)"', free)))
    assert positions["all_in"] == ("left", "top")
    assert positions["fold"] == ("left", "bottom")
    assert positions["aggressive"] == ("right", "bottom")


def test_the_maximum_raise_does_not_print_all_in_twice():
    """Raising to the maximum is all-in, and the label used to change to say
    so -- which, now that all-in has a slot of its own, put the same word on
    two of the four buttons."""
    table = Path("static/v038-poker8-v2-cinematic-table.js").read_text(encoding="utf-8")
    assert "const hasAllInSlot = defs.some(def => def.key === \"all_in\");" in table
    assert "if (aggressive && atMax && !hasAllInSlot) {" in table


def test_the_trainer_controls_are_gone_from_an_online_drawer():
    """Online the server deals, starts the next hand and never pauses, so
    "Новая раздача", "∞ Бесконечный режим" and "Пауза / продолжить" did
    nothing there. Hidden by mode, not deleted -- the local trainer still
    uses all three -- and the divider goes with them or it opens the
    drawer."""
    for control in ("#mobileDrawerNewHand", "#mobileDrawerInfinite",
                    "#mobileDrawerPause", ".mobile-drawer-divider"):
        assert f".poker8-online {control}" in ONLINE, control
    markup = Path("static/index.html").read_text(encoding="utf-8")
    assert 'id="mobileDrawerInfinite"' in markup, "the trainer still needs them"


def test_one_door_to_the_guide_and_it_holds_all_three_parts():
    """A second "Инструкция" button sat under the seat count for a while,
    opening the panel the header's "?" already opens -- the same door twice,
    two controls apart in the same bar. The identity is name and blinds."""
    assert "p8TableGuide" not in ONLINE
    assert '"#mobileHintButton"' in ONLINE
    identity = ONLINE[ONLINE.index("box.innerHTML = '<b data-name>"):]
    assert "button" not in identity[:identity.index(";")]

    v037 = Path("static/table-guide.js").read_text(encoding="utf-8")
    for section in ("Комбинации", "Правила", "Кнопки"):
        assert f'<h4 class="hr-section">{section}</h4>' in v037, section
    for key in ("FOLD", "CHECK", "CALL", "BET / RAISE", "ALL-IN"):
        assert f'["{key}"' in v037.replace('["', '["'), key


def test_each_action_wears_its_own_buttons_colour():
    """The names read as plain text next to five differently coloured
    buttons. --act-* live in style.css, which the lobby never loads, so each
    rule carries the same literal as its fallback."""
    guide = Path("static/table-guide.js").read_text(encoding="utf-8")
    # check and call share one rule, so match the pairing rather than a
    # selector-by-selector shape.
    for cls, var, literal in (("fold", "--act-fold", "#ff4d42"),
                              ("check", "--act-check", "#49caff"),
                              ("call", "--act-check", "#49caff"),
                              ("bet", "--act-raise", "#55f16e"),
                              ("allin", "--act-allin", "#ffc44d")):
        assert f".hr-act-{cls} strong" in guide, cls
        assert f"color:var({var},{literal})" in guide, (cls, var)
    table = Path("static/v038-poker8-v2-cinematic-table.js").read_text(encoding="utf-8")
    for cls, var in (("fold", "--act-fold"), ("call", "--act-check"), ("all-in", "--act-allin")):
        assert f".action-slot.{cls}{{--v038-action:var({var});}}" in table, cls


def test_the_lobby_offers_the_same_panel_before_anyone_sits_down():
    """It lived in v037, which the lobby never loads -- and the lobby is
    where somebody is most likely to want it."""
    for page in ("static/index.html", "static/lobby.html"):
        assert "table-guide.js?v=" in Path(page).read_text(encoding="utf-8"), page
    lobby = Path("static/lobby.js").read_text(encoding="utf-8")
    assert 'window.Poker8TableGuide?.toggle()' in lobby
    assert "window.Poker8TableGuide?.close()" in lobby
    v037 = Path("static/v037-poker8-v2-reference-table.js").read_text(encoding="utf-8")
    assert "HAND_RANKINGS" not in v037, "one copy, or the two pages drift"
    assert "window.Poker8TableGuide?.ensure();" in v037


def test_a_tap_anywhere_on_a_table_card_opens_it():
    """"Войти" is a small target inside something that already looks
    pressable, so on a phone every tap that landed beside it did nothing.
    The close-room "×" is the one part of a card that means something else."""
    lobby = Path("static/lobby.js").read_text(encoding="utf-8")
    assert 'data-open-table="${escape(table.id)}"' in lobby
    handler = lobby[lobby.index('.table-card[data-open-table]'):]
    handler = handler[:handler.index("}));") + 4]
    assert 'closest?.("[data-close-room]")' in handler
    assert "openTable(card.dataset.openTable)" in handler
    css = Path("static/network.css").read_text(encoding="utf-8")
    assert ".table-card[data-open-table]{cursor:pointer}" in css


def test_the_instruction_uses_the_whole_height_it_has():
    """Centred at 82vh, half the spare height went above the panel and the
    list was cut off partway down the combinations on a phone. Pinned near
    the top it gets everything the viewport has -- measured at 690px: the
    panel runs 8..682 and the tenth combination ends at 553, so all ten are
    there without scrolling."""
    guide = Path("static/table-guide.js").read_text(encoding="utf-8")
    panel = guide[guide.index(".hand-rankings-modal .hr-panel{"):]
    panel = panel[:panel.index("}")]
    assert "top:8px" in panel and "transform:translateX(-50%)" in panel
    assert "top:50%" not in panel, "centring is what spent the height"
    # dvh, or a browser's collapsing chrome takes a slice of it.
    assert "max-height:calc(100dvh - 16px)" in panel


def test_the_boot_veil_covers_the_whole_page_at_every_width():
    """It hung off .app-shell::after behind a max-width query, so the mobile
    header ("СТОЛ", "Новая раздача") and the bet bar -- .app-shell's own
    siblings -- painted their pre-v2 selves around it, and at desktop width
    nothing was covered at all."""
    index = Path("static/index.html").read_text(encoding="utf-8")
    # Rules only: the comment above them names what it replaced, in the same
    # words these assertions look for.
    style = re.sub(r"/\*.*?\*/", "", index[index.index("<style>"):index.index("</style>")], flags=re.S)
    assert "body:not(.p8-boot-ready)::after" in style
    assert ".app-shell::after" not in style
    assert "@media (max-width: 780px)" not in style, "the veil must not be width-gated"
    assert "z-index: 999" in style
    # And a failsafe, so a layer that never reports ready cannot leave a
    # permanently blank page.
    assert 'window.setTimeout(() => document.body.classList.add("p8-boot-ready"), 3000);' in index
