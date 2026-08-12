from pathlib import Path

from persistence.store import TrainingStore
from poker.engine import PokerEngine


def test_new_bot_on_reused_empty_seat_gets_fresh_id_and_deposit(tmp_path: Path):
    store = TrainingStore(tmp_path / 'db.sqlite3')
    first = store.add_bot(4, 'Первый', 'normal')
    first_id = first['id']
    store.set_balance(first_id, 0.0)
    store.clear_seat(4)

    second = store.add_bot(4, 'Второй', 'hard')
    assert second['id'] != first_id
    assert second['balance'] == store.INITIAL_BALANCE


def test_single_human_cards_can_be_revealed_during_bot_turn(tmp_path: Path):
    # Regression assertion for the public-state capability used by v0.10.1:
    # a chosen viewer keeps their own cards visible even when another player acts.
    store = TrainingStore(tmp_path / 'db.sqlite3')
    store.add_bot(1, 'Бот', 'normal')
    engine = PokerEngine()
    state = engine.new_hand(store.active_seats(), button_seat=0)
    human = next(p for p in state.players.values() if not p.is_bot)
    bot = next(p for p in state.players.values() if p.is_bot)
    state.acting_player = bot.id
    payload = state.to_dict(viewer_player_id=human.id)
    assert payload['players'][human.id]['hole_cards'] != ['??', '??']
    assert payload['players'][bot.id]['hole_cards'] == ['??', '??']


def test_v037_reference_table_pass_is_loaded_and_chat_is_decorative():
    root = Path(__file__).resolve().parents[1]
    source = (root / 'static' / 'v037-poker8-v2-reference-table.js').read_text(encoding='utf-8')
    loader = (root / 'static' / 'v036-poker8-v2-prehand-pass.js').read_text(encoding='utf-8')

    assert '/static/v037-poker8-v2-reference-table.js' in loader
    assert 'data-v037-poker8-v2-reference-table' in loader
    assert 'id = "mobileChatButton"' in source
    assert 'setAttribute("aria-label"' in source
    assert 'type = "button"' in source
    assert 'addEventListener("click"' not in source
    assert 'window.addEventListener("resize", start)' in source
    assert '@media (max-width:780px)' in source
