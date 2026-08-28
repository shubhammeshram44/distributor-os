"""add_unique_constraint_on_shipments_tenant_order

Fix for SHIP-5: create_shipment (the batch dispatch endpoint) checked for
an existing Shipment for the order via a plain check-then-insert SELECT,
with no application-level lock and no DB-level constraint backing it -- a
classic TOCTOU race. Two near-simultaneous dispatch requests for the same
order (e.g. a double-submit from an impatient back-office user, or two
staff members dispatching from different tabs) could both pass the
existence check before either commits, creating two Shipment rows (and two
OrderStateLedger "Dispatched" transitions) for what must always be exactly
one order-to-shipment relationship.

Adds a unique constraint on shipments(tenant_id, order_id). The API layer
(shipments.py::create_shipment) now runs each order's insert inside its own
SAVEPOINT and catches the resulting IntegrityError, skipping just that
order (its shipment already exists) while still committing shipments for
the rest of the batch -- closing the race instead of moving where
duplicates would surface.

A separate NON-unique index (ix_shipments_tenant_order, from
b44937b13012) already exists on the same two columns for query performance
-- left in place rather than replaced, to keep this change minimal;
Postgres/SQLite will simply maintain both, which has negligible overhead
for a table of this size.

Revision ID: e7f8a9b0c1d2
Revises: d6e7f8a9b0c1
Create Date: 2026-09-05 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import logging

from app.utils.migration_helpers import (
    index_exists,
    unique_constraint_exists,
    drop_unique_index_or_constraint,
)

logger = logging.getLogger(__name__)

# revision identifiers, used by Alembic.
revision: str = 'e7f8a9b0c1d2'
down_revision: Union[str, Sequence[str], None] = 'd6e7f8a9b0c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SHIPMENTS_UNIQUE_NAME = 'uq_shipments_tenant_order'


def upgrade() -> None:
    bind = op.get_bind()
    if index_exists(bind, 'shipments', _SHIPMENTS_UNIQUE_NAME) or \
       unique_constraint_exists(bind, 'shipments', _SHIPMENTS_UNIQUE_NAME):
        return

    duplicate_count = bind.execute(sa.text(
        "SELECT COUNT(*) FROM ("
        "  SELECT tenant_id, order_id FROM shipments "
        "  GROUP BY tenant_id, order_id HAVING COUNT(*) > 1"
        ") dupes"
    )).scalar()
    if duplicate_count:
        # Defensive, consistent with this project's other constraint-adding
        # migrations (see INV-6/INV-7 in d6e7f8a9b0c1): don't fail outright
        # on a database that already has the exact problem this migration
        # is trying to prevent going forward.
        logger.warning(
            "Skipping unique constraint %s: %d existing duplicate "
            "(tenant_id, order_id) pair(s) found in shipments. Clean up "
            "duplicate shipments, then re-run this migration (or apply the "
            "constraint manually) to close this gap.",
            _SHIPMENTS_UNIQUE_NAME, duplicate_count,
        )
        return

    op.create_index(_SHIPMENTS_UNIQUE_NAME, 'shipments', ['tenant_id', 'order_id'], unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    if index_exists(bind, 'shipments', _SHIPMENTS_UNIQUE_NAME) or \
       unique_constraint_exists(bind, 'shipments', _SHIPMENTS_UNIQUE_NAME):
        drop_unique_index_or_constraint(bind, 'shipments', _SHIPMENTS_UNIQUE_NAME)
