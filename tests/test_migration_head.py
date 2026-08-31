from alembic.script import ScriptDirectory

from app.online import BASE_DIR, EXPECTED_MIGRATION_REVISION


def test_startup_requires_the_latest_migration():
    scripts = ScriptDirectory(str(BASE_DIR / "migrations"))
    assert EXPECTED_MIGRATION_REVISION == scripts.get_current_head()
