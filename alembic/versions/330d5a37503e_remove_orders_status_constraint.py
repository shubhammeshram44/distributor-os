"""remove_orders_status_constraint

Revision ID: 330d5a37503e
Revises: 1acdb3068945
Create Date: 2026-07-19 21:27:30.212208

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '330d5a37503e'
down_revision: Union[str, Sequence[str], None] = '1acdb3068945'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "postgresql":
        # Alter the column type to VARCHAR(50) explicitly in case it was a custom enum type
        op.execute("ALTER TABLE orders ALTER COLUMN status TYPE VARCHAR(50) USING status::varchar;")
        op.execute("ALTER TABLE order_state_ledger ALTER COLUMN from_status TYPE VARCHAR(50) USING from_status::varchar;")
        op.execute("ALTER TABLE order_state_ledger ALTER COLUMN to_status TYPE VARCHAR(50) USING to_status::varchar;")
        
        # Drop CHECK constraints on orders.status
        op.execute("""
            DO $$
            DECLARE
                r RECORD;
            BEGIN
                FOR r IN
                    SELECT tc.constraint_name
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.constraint_column_usage ccu
                      ON tc.constraint_name = ccu.constraint_name
                    WHERE tc.table_name = 'orders'
                      AND ccu.column_name = 'status'
                      AND tc.constraint_type = 'CHECK'
                LOOP
                    EXECUTE 'ALTER TABLE orders DROP CONSTRAINT ' || quote_ident(r.constraint_name);
                END LOOP;
            END $$;
        """)
        
        # Drop CHECK constraints on order_state_ledger.from_status / to_status
        op.execute("""
            DO $$
            DECLARE
                r RECORD;
            BEGIN
                FOR r IN
                    SELECT tc.constraint_name
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.constraint_column_usage ccu
                      ON tc.constraint_name = ccu.constraint_name
                    WHERE tc.table_name = 'order_state_ledger'
                      AND ccu.column_name IN ('from_status', 'to_status')
                      AND tc.constraint_type = 'CHECK'
                LOOP
                    EXECUTE 'ALTER TABLE order_state_ledger DROP CONSTRAINT ' || quote_ident(r.constraint_name);
                END LOOP;
            END $$;
        """)


def downgrade() -> None:
    """Downgrade schema."""
    pass

