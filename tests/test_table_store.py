from persistence import TrainingStore


def test_six_bot_seats_can_be_activated(tmp_path):
    store = TrainingStore(tmp_path / "trainer.sqlite3")
    for seat in range(1, 7):
        store.add_bot(seat, f"Test {seat}", "hard")
    table = store.get_table()
    assert len([row for row in table if row["active"]]) == 7
    assert all(row["balance"] == 1000.0 for row in table)


def test_bot_balance_survives_edit_while_seated(tmp_path):
    store = TrainingStore(tmp_path / "trainer.sqlite3")
    row = store.add_bot(3, "Макс", "maximum")
    store.set_balance(row["id"], 1234.5)
    store.update_bot(3, "Макс 2", "hard")
    row = next(x for x in store.get_table() if x["seat"] == 3)
    assert row["balance"] == 1234.5
    assert row["difficulty"] == "hard"
