from persistence import TrainingStore


def test_six_bot_seats_can_be_activated_when_human_leaves(tmp_path):
    store = TrainingStore(tmp_path / "trainer.sqlite3")
    store.clear_seat(0)

    for seat in range(1, 7):
        store.add_bot(seat, f"Test {seat}", "hard")

    active = [row for row in store.get_table() if row["active"]]
    assert len(active) == 6
    assert all(row["occupant_type"] == "bot" for row in active)


def test_bot_balance_survives_edit_while_seated(tmp_path):
    store = TrainingStore(tmp_path / "trainer.sqlite3")
    row = store.add_bot(3, "Макс", "maximum")
    store.set_balance(row["id"], 1234.5)
    store.update_bot(3, "Макс 2", "hard")
    row = next(x for x in store.get_table() if x["seat"] == 3)
    assert row["balance"] == 1234.5
    assert row["difficulty"] == "hard"
