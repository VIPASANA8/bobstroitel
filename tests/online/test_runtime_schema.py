from online.schema import game_commands, hand_actions, hand_players, hands, integrity_events, table_runtimes


def test_runtime_schema_has_recovery_and_idempotency_keys():
    assert table_runtimes.c.table_id.primary_key
    assert table_runtimes.c.revision.nullable is False
    assert {column.name for column in game_commands.primary_key.columns} == {"table_id", "command_id"}
    assert "private_state_json" in table_runtimes.c
    assert "public_payload_json" in integrity_events.c
