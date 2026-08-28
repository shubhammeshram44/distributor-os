"""add_sku_uniqueness_inventory_check_and_dashboard_indexes

Fix for INV-6: no DB-level uniqueness existed on products.sku_id (or
(tenant_id, sku_id)) anywhere in the schema -- only an app-side
check-then-insert (products.py's create_product/import_products_csv)
guarded against duplicates, which is race-prone: concurrent product
creation/import for the same SKU can both pass the existence check and
both insert, producing two Product rows (and two independent Inventory
rows) for what should be one SKU, splitting real stock across duplicate
catalog entries and confusing alias/order-matching logic that assumes one
product per SKU.

Fix for INV-7: Inventory.quantity_on_hand had no CHECK constraint or any
DB-level floor -- the only thing preventing negative values was the
`allocated = min(item.quantity, available)` clamp inside confirm_order
(and equivalent clamps in allocation_queue_service.py), which INV-1
already showed can be bypassed by a concurrency race if the clamp reads a
stale snapshot. A CHECK constraint gives a genuine last line of defense
at the database layer instead of relying entirely on application logic
that has already been shown to be insufficient under concurrency.

Both are added DEFENSIVELY: since these are new constraints being applied
to potentially-existing production data (whose duplicate-SKU / negative-
stock state this migration cannot know in advance), each checks for
violations first and skips adding the constraint (logging a warning
instead of raising) if any already exist -- so this migration can never
fail outright and block deployment on a database that already has the
exact data-integrity problem it's trying to prevent going forward. A
follow-up data-cleanup pass would be needed to actually enable the
constraint on such a database; this migration surfaces that need via the
warning rather than silently reverting to the old (dangerous) behavior.

Fix for DB-3: adds composite indexes orders(tenant_id, created_at) and
orders(tenant_id, status) -- only single-column ix_orders_tenant_id and
ix_orders_created_at existed before, but dashboard.py's queries (metrics,
overview, business-health-score, decision-focus, etc.) consistently
filter on tenant_id + created_at or tenant_id + status TOGETHER. At
scale, Postgres can only use one of the two single-column indexes per
query and must filter the remainder of a tenant's full order set
row-by-row -- the severe-slowdown risk explicitly named in the original
audit.

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
Create Date: 2026-08-28 14:30:00.000000

"""
from typing import Sequence, Union
import logging

from alembic import op
import sqlalchemy as sa

from app.utils.migration_helpers import index_exists, unique_constraint_exists, drop_unique_index_or_constraint

logger = logging.getLogger("alembic.runtime.migration")

# revision identifiers, used by Alembic.
revision: str = 'd6e7f8a9b0c1'
down_revision: Union[str, Sequence[str], None] = 'c5d6e7f8a9b0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PRODUCTS_SKU_INDEX = 'uq_products_tenant_sku_id'
_INVENTORY_NONNEG_CHECK = 'ck_inventory_quantity_on_hand_nonneg'


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # ── INV-6: unique (tenant_id, sku_id) on products ───────────────────────
    if not index_exists(bind, 'products', _PRODUCTS_SKU_INDEX) and \
       not unique_constraint_exists(bind, 'products', _PRODUCTS_SKU_INDEX):
        duplicate_count = bind.execute(sa.text(
            "SELECT COUNT(*) FROM ("
            "  SELECT tenant_id, sku_id FROM products "
            "  GROUP BY tenant_id, sku_id HAVING COUNT(*) > 1"
            ") dupes"
        )).scalar()
        if duplicate_count:
            logger.warning(
                "Skipping unique index %s: %d existing duplicate (tenant_id, sku_id) "
                "pair(s) found in products. Clean up duplicate SKUs, then re-run this "
                "migration (or apply the index manually) to close this gap.",
                _PRODUCTS_SKU_INDEX, duplicate_count,
            )
        else:
            op.create_index(_PRODUCTS_SKU_INDEX, 'products', ['tenant_id', 'sku_id'], unique=True)

    # ── INV-7: CHECK (quantity_on_hand >= 0) on inventory ───────────────────
    existing_checks = {c['name'] for c in inspector.get_check_constraints('inventory')} if 'inventory' in inspector.get_table_names() else set()
    if _INVENTORY_NONNEG_CHECK not in existing_checks:
        negative_count = bind.execute(sa.text(
            "SELECT COUNT(*) FROM inventory WHERE quantity_on_hand < 0"
        )).scalar()
        if negative_count:
            logger.warning(
                "Skipping CHECK constraint %s: %d existing inventory row(s) with "
                "negative quantity_on_hand found. Clean up negative stock, then "
                "re-run this migration (or apply the constraint manually) to close "
                "this gap.",
                _INVENTORY_NONNEG_CHECK, negative_count,
            )
        else:
            op.create_check_constraint(_INVENTORY_NONNEG_CHECK, 'inventory', 'quantity_on_hand >= 0')

    # ── DB-3: composite indexes for the exact predicates dashboard queries
    # actually use (tenant_id, created_at) and (tenant_id, status) together.
    # Only single-column ix_orders_tenant_id / ix_orders_created_at existed
    # before this -- at scale, Postgres can only use one of the two
    # single-column indexes per query and must filter the rest of a
    # tenant's full order set row-by-row.
    if not index_exists(bind, 'orders', 'ix_orders_tenant_created_at'):
        op.create_index('ix_orders_tenant_created_at', 'orders', ['tenant_id', 'created_at'])
    if not index_exists(bind, 'orders', 'ix_orders_tenant_status'):
        op.create_index('ix_orders_tenant_status', 'orders', ['tenant_id', 'status'])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if index_exists(bind, 'orders', 'ix_orders_tenant_status'):
        op.drop_index('ix_orders_tenant_status', table_name='orders')
    if index_exists(bind, 'orders', 'ix_orders_tenant_created_at'):
        op.drop_index('ix_orders_tenant_created_at', table_name='orders')

    if index_exists(bind, 'products', _PRODUCTS_SKU_INDEX) or \
       unique_constraint_exists(bind, 'products', _PRODUCTS_SKU_INDEX):
        drop_unique_index_or_constraint(bind, 'products', _PRODUCTS_SKU_INDEX)

    existing_checks = {c['name'] for c in inspector.get_check_constraints('inventory')} if 'inventory' in inspector.get_table_names() else set()
    if _INVENTORY_NONNEG_CHECK in existing_checks:
        op.drop_constraint(_INVENTORY_NONNEG_CHECK, 'inventory', type_='check')
