"""
InventoryLedgerService — append-only audit trail for stock mutations.

Fix for INV-3: previously no record survived past whatever an in-memory
logger.info() call happened to log (if anything) when Inventory.quantity_on_hand
changed -- there was no way to answer "why does this SKU have this many units"
after the fact. Mirrors the CustomerLedger / ledger_service.py pattern already
established in this codebase: inventory_ledgers is the append-only source of
truth for HISTORY, while Inventory.quantity_on_hand remains the fast, mutable
CURRENT-STATE cache that order confirmation/allocation/etc. already read.

This module does not compute or apply quantity changes itself -- callers
still mutate Inventory directly (unchanged from before this fix, to keep
each call site's existing logic/locking behavior intact) and then call
record_inventory_movement() with the delta they just applied and the
resulting quantity_on_hand, so this is purely additive logging with no
change to existing stock-mutation behavior.
"""
import uuid
import logging
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.inventory_ledger import InventoryLedger

logger = logging.getLogger(__name__)


def record_inventory_movement(
    db: Session,
    tenant_id: uuid.UUID,
    sku_id: uuid.UUID,
    quantity_delta: int,
    quantity_on_hand_after: int,
    movement_type: str,
    reference_id: str | None = None,
    notes: str | None = None,
) -> InventoryLedger | None:
    """Records one inventory movement. No-op (returns None) for a zero delta
    -- a movement that changes nothing isn't a real event worth an audit row."""
    if quantity_delta == 0:
        return None

    entry = InventoryLedger(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        sku_id=sku_id,
        quantity_delta=quantity_delta,
        quantity_on_hand_after=quantity_on_hand_after,
        movement_type=movement_type,
        reference_id=reference_id,
        notes=notes,
        created_at=datetime.utcnow(),
    )
    db.add(entry)
    logger.info(
        "Inventory movement: sku=%s type=%s delta=%+d after=%d ref=%s",
        sku_id, movement_type, quantity_delta, quantity_on_hand_after, reference_id,
    )
    return entry
