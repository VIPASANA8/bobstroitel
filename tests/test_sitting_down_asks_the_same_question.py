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
V037 = Path("static/v037-poker8-v2-reference-table.js").read_text(encoding="utf-8")


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


def test_the_instruction_sits_under_the_seat_count_and_holds_all_three_parts():
    """"2 из 6 мест" is where somebody looking for help is already looking.
    It opens the same panel the header's "?" does, so there is one place
    holding what beats what, how a hand runs, and what each button does."""
    assert 'id="p8TableGuide"' in ONLINE
    assert '"#mobileHintButton, #p8TableGuide"' in ONLINE
    identity = ONLINE[ONLINE.index("box.innerHTML = '<b data-name>"):]
    assert "p8TableGuide" in identity[:identity.index(";")], "not under the count"

    v037 = Path("static/v037-poker8-v2-reference-table.js").read_text(encoding="utf-8")
    for section in ("Комбинации", "Правила", "Кнопки"):
        assert f'<h4 class="hr-section">{section}</h4>' in v037, section
    for key in ("FOLD", "CHECK", "CALL", "BET / RAISE", "ALL-IN"):
        assert f'["{key}"' in v037.replace('["', '["'), key
