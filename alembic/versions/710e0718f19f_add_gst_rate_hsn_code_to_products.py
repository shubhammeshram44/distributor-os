"""add_gst_rate_hsn_code_to_products

Adds GST-compliance columns:
- products.gst_rate / products.hsn_code — per-product GST rate (was hardcoded
  at 18% everywhere) and HSN code for line-item printing on tax invoices.
- invoices.cgst_amount / invoices.sgst_amount — CGST/SGST split (previously
  only a single combined "GST" total was shown, which is not a legally valid
  breakdown for an intra-state GST tax invoice).
- invoices.invoice_number — sequential financial-year invoice number
  (e.g. INV/2026-27/001), previously invoices only had an ad-hoc
  "INV-{internal_order_id}" string generated at PDF-render time, not a real
  persisted sequential number.

Uses the project's column_exists() idempotency helper (see
app/utils/migration_helpers.py) so this applies cleanly against both a fresh
database and one where these columns were already created out-of-band.

Revision ID: 710e0718f19f
Revises: f2a3b4c5d6e7
Create Date: 2026-07-19 09:34:11.005898

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.utils.migration_helpers import column_exists, index_exists

# revision identifiers, used by Alembic.
revision: str = '710e0718f19f'
down_revision: Union[str, Sequence[str], None] = 'f2a3b4c5d6e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()

    if not column_exists(bind, 'products', 'gst_rate'):
        with op.batch_alter_table('products') as batch_op:
            batch_op.add_column(
                sa.Column('gst_rate', sa.Numeric(5, 2), nullable=False, server_default=sa.text('18.0'))
            )

    if not column_exists(bind, 'products', 'hsn_code'):
        with op.batch_alter_table('products') as batch_op:
            batch_op.add_column(
                sa.Column('hsn_code', sa.String(20), nullable=True)
            )

    if not column_exists(bind, 'invoices', 'cgst_amount'):
        with op.batch_alter_table('invoices') as batch_op:
            batch_op.add_column(
                sa.Column('cgst_amount', sa.Numeric(10, 2), nullable=True)
            )

    if not column_exists(bind, 'invoices', 'sgst_amount'):
        with op.batch_alter_table('invoices') as batch_op:
            batch_op.add_column(
                sa.Column('sgst_amount', sa.Numeric(10, 2), nullable=True)
            )

    if not column_exists(bind, 'invoices', 'invoice_number'):
        with op.batch_alter_table('invoices') as batch_op:
            batch_op.add_column(
                sa.Column('invoice_number', sa.String(50), nullable=True)
            )

    # Uniqueness scoped per tenant (NULLs — pre-migration invoices, or any
    # future edge case — are exempt from the unique constraint under normal
    # SQL semantics, so this is safe to add before any backfill).
    if not index_exists(bind, 'invoices', 'ix_invoices_tenant_invoice_number'):
        op.create_index(
            'ix_invoices_tenant_invoice_number',
            'invoices',
            ['tenant_id', 'invoice_number'],
            unique=True
        )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    if index_exists(bind, 'invoices', 'ix_invoices_tenant_invoice_number'):
        op.drop_index('ix_invoices_tenant_invoice_number', table_name='invoices')

    with op.batch_alter_table('invoices') as batch_op:
        batch_op.drop_column('invoice_number')
        batch_op.drop_column('sgst_amount')
        batch_op.drop_column('cgst_amount')

    with op.batch_alter_table('products') as batch_op:
        batch_op.drop_column('hsn_code')
        batch_op.drop_column('gst_rate')
