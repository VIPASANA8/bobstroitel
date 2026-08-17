from online.integrity import EscrowMismatch


def test_a_mismatch_keeps_its_identity_while_the_amounts_move():
    """One standing mismatch must stay one finding, or it alerts on every check."""
    first = EscrowMismatch("micro-a", "table_user_escrow", expected_units=0, actual_units=4150)
    later = EscrowMismatch("micro-a", "table_user_escrow", expected_units=4100, actual_units=8250)

    assert first.fingerprint == later.fingerprint


def test_different_tables_and_participants_stay_separate():
    table_a = EscrowMismatch("micro-a", "table_user_escrow", 0, 100)
    table_b = EscrowMismatch("micro-b", "table_user_escrow", 0, 100)
    bot = EscrowMismatch("micro-a", "system_player_escrow", 0, 100, participant_id="bot-1")

    assert len({table_a.fingerprint, table_b.fingerprint, bot.fingerprint}) == 3


def test_payload_still_carries_the_current_amounts():
    finding = EscrowMismatch("micro-a", "table_user_escrow", expected_units=0, actual_units=4150)

    assert finding.payload()["actual_units"] == 4150
    assert finding.payload()["difference_units"] == -4150
