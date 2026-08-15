import json
import logging

from online.logging import JsonFormatter, redact_event


def test_structured_events_redact_private_and_telegram_fields():
    payload = redact_event({
        "tenant_id": "tenant", "table_id": "t1", "user_id": "u1", "telegram_user_id": 101,
        "bot_token": "secret", "cookie": "cookie", "hole_cards": ["As", "Ah"],
        "private_state_json": {"deck_cards": ["Kd"]},
    })
    encoded = json.dumps(payload)
    assert "101" not in encoded and "secret" not in encoded and "As" not in encoded
    assert payload["table_id"] == "t1"


def test_json_formatter_outputs_machine_readable_event():
    record = logging.LogRecord("test", logging.INFO, __file__, 1, "command_accepted", (), None)
    record.event_payload = {"command_id": "cmd-1", "cookie": "secret"}
    payload = json.loads(JsonFormatter().format(record))
    assert payload["event"] == "command_accepted"
    assert payload["cookie"] == "[REDACTED]"
