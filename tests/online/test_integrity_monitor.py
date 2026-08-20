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


def test_the_fingerprint_survives_a_round_trip_through_the_event_log():
    """Warm-up rebuilds the open set from recorded payloads, so the fingerprint
    it derives from a payload has to match the finding's own."""
    from online.integrity import EscrowIntegrityMonitor

    bot = EscrowMismatch("micro-a", "system_player_escrow", 100, 120, participant_id="bot-1")
    table = EscrowMismatch("micro-a", "table_user_escrow", 0, 4150)

    assert EscrowIntegrityMonitor._fingerprint_of(bot.payload()) == bot.fingerprint
    assert EscrowIntegrityMonitor._fingerprint_of(table.payload()) == table.fingerprint


def test_a_standing_mismatch_is_not_reported_again_after_a_restart():
    """The open set lives in memory, so every restart used to forget every
    standing mismatch and report it as brand new -- a duplicate event and a
    fresh alert per finding on each deploy."""
    import anyio
    from online.integrity import EscrowIntegrityMonitor

    standing = EscrowMismatch("micro-a", "system_player_escrow", 100, 120, participant_id="bot-1")
    fixed = EscrowMismatch("micro-b", "table_user_escrow", 0, 500)

    class _Rows:
        def __init__(self, rows): self._rows = rows
        def mappings(self): return self
        def all(self): return self._rows

    class _Session:
        async def execute(self, _query):
            return _Rows([
                {"event_type": "escrow_stack_mismatch", "public_payload_json": standing.payload()},
                {"event_type": "escrow_stack_mismatch", "public_payload_json": fixed.payload()},
                {"event_type": "escrow_stack_mismatch_resolved", "public_payload_json": fixed.payload()},
            ])

    monitor = EscrowIntegrityMonitor(session_factory=None)
    anyio.run(monitor._warm_open_findings, _Session())

    # Still open, so it must not be announced again...
    assert standing.fingerprint in monitor._open_findings
    # ...while one already resolved is forgotten, and would be news if it returned.
    assert fixed.fingerprint not in monitor._open_findings

    # And warm-up happens once per process, not on every check.
    monitor._open_findings = {}
    anyio.run(monitor._warm_open_findings, _Session())
    assert monitor._open_findings == {}
