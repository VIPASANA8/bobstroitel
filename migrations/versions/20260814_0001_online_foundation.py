"""Create the online foundation schema."""

from alembic import op

from online.schema import metadata


revision = "20260814_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    metadata.create_all(bind=bind)
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            CREATE OR REPLACE FUNCTION poker8_require_balanced_posted_transaction()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                IF NEW.status = 'posted' AND COALESCE(
                    (SELECT SUM(amount_units) FROM play_entries WHERE transaction_id = NEW.id), 0
                ) <> 0 THEN
                    RAISE EXCEPTION 'posted play transaction must be balanced';
                END IF;
                RETURN NEW;
            END;
            $$;
            """
        )
        op.execute(
            """
            CREATE CONSTRAINT TRIGGER play_transaction_balance_check
            AFTER UPDATE OF status ON play_transactions
            DEFERRABLE INITIALLY DEFERRED
            FOR EACH ROW
            WHEN (NEW.status = 'posted')
            EXECUTE FUNCTION poker8_require_balanced_posted_transaction();
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS play_transaction_balance_check ON play_transactions")
        op.execute("DROP FUNCTION IF EXISTS poker8_require_balanced_posted_transaction()")
    metadata.drop_all(bind=bind)
