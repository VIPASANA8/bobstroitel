"""The felt had no reference for what beats what -- a button next to chat
opens a static hand-rankings modal, highest to lowest."""

import json
import subprocess
import tempfile
from pathlib import Path

SOURCE = Path("static/v037-poker8-v2-reference-table.js").read_text(encoding="utf-8")
ONLINE_TABLE = Path("static/online-table.js").read_text(encoding="utf-8")


def test_the_hint_button_sits_next_to_chat_in_one_header_group():
    assert '"mobileHeaderUtility"' in SOURCE
    assert 'utility.appendChild(chat)' in SOURCE
    assert 'utility.appendChild(hint)' in SOURCE
    assert 'hint.id = "mobileHintButton"' in SOURCE


def test_the_headers_own_order_rule_moved_to_the_group_not_the_chat_button():
    """.mobile-chat-button{order:2} used to force chat to the end of
    #mobileGameHeader's own flex row, back when it sat there directly next to
    #mobileHeaderSeatActions. Now that chat lives one level deeper, inside
    .mobile-header-utility, an order left on the button only reorders it
    against its one sibling in that inner row (the hint button) -- which is
    exactly the bug this caught: the hint rendered to the LEFT of chat,
    because order:2 beat the hint's default order:0 inside their shared
    flex container, though the two were appended chat-then-hint."""
    assert ".mobile-chat-button{order:2}" not in ONLINE_TABLE
    assert ".mobile-header-utility{order:2}" in ONLINE_TABLE


def test_v037_stays_decorative_like_the_chat_button():
    """v037 runs before online-table.js's own init, so a click handler bound
    to an element it just created here found nothing (see the chat button's
    own delegated listener) -- the hint button and its modal follow the same
    rule: build the DOM, wire nothing."""
    assert 'addEventListener("click"' not in SOURCE


def test_the_modal_opens_and_closes_three_ways_delegated_off_document():
    body = ONLINE_TABLE[ONLINE_TABLE.index('"#mobileHintButton"') - 200:]
    body = body[:body.index("modal.hidden = true;\n    });") + 30]
    assert 'modal.hidden = false;' in body
    assert '".hr-backdrop, #handRankingsClose"' in body
    assert 'event.key === "Escape"' in ONLINE_TABLE
    assert 'modal && !modal.hidden) modal.hidden = true;' in ONLINE_TABLE


def test_the_rankings_are_ten_hands_highest_to_lowest_with_five_real_cards_each():
    """Extracts and evaluates the real HAND_RANKINGS array plus miniCardHtml,
    so a typo'd card code (bad rank/suit letter) fails loudly instead of
    silently rendering a blank or mislabelled card."""
    start = SOURCE.index("const HAND_RANKINGS")
    end = SOURCE.index("];", start) + 2
    data = SOURCE[start:end]

    harness = data + "\nconsole.log(JSON.stringify(HAND_RANKINGS));"
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
        handle.write(harness)
        path = handle.name
    result = subprocess.run(["node", path], capture_output=True, text=True, encoding="utf-8", check=True)
    hands = json.loads(result.stdout)

    assert [h["name"] for h in hands] == [
        "Роял-флеш", "Стрит-флеш", "Каре", "Фулл-хаус", "Флеш",
        "Стрит", "Сет", "Две пары", "Пара", "Старшая карта",
    ]
    valid_ranks = set("23456789TJQKA")
    valid_suits = set("shdc")
    for hand in hands:
        assert len(hand["cards"]) == 5, hand["name"]
        for code in hand["cards"]:
            assert len(code) == 2 and code[0] in valid_ranks and code[1] in valid_suits, (hand["name"], code)
