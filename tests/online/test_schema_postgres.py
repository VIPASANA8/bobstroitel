from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from online.schema import hand_players, hands, system_players, tenant_bots


def test_boolean_defaults_compile_as_postgres_booleans():
    dialect = postgresql.dialect()

    assert "active BOOLEAN DEFAULT true NOT NULL" in str(CreateTable(system_players).compile(dialect=dialect))
    assert "enabled BOOLEAN DEFAULT true NOT NULL" in str(CreateTable(tenant_bots).compile(dialect=dialect))
    assert "terminal BOOLEAN DEFAULT false NOT NULL" in str(CreateTable(hands).compile(dialect=dialect))
    hand_players_sql = str(CreateTable(hand_players).compile(dialect=dialect))
    assert "shown BOOLEAN DEFAULT false NOT NULL" in hand_players_sql
    assert "folded BOOLEAN DEFAULT false NOT NULL" in hand_players_sql
