"""
LedgerService — Single source of truth for all customer financial transactions.

ARCHITECTURE DECISION:
- customer_ledgers table is the source of truth (append-only transaction log)
- customers.outstanding_balance is a computed cache (never update directly)
- ALL financial transactions must go through record_transaction()
- outstanding_balance is always recomputed from ledger after each transaction

This prevents the sync issues that occur when outstanding_balance and
customer_ledgers get out of sync (e.g. cancellation without reversal).
"""

import uuid
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func, case

from app.models.customer import Customer
from app.models.ledger import CustomerLedger

logger = logging.getLogger(__name__)


def record_transaction(
    db: Session,
    tenant_id: uuid.UUID,
    customer_id: uuid.UUID,
    type: str,
    amount: float,
    reference_id: str,
    description: str = ""
) -> CustomerLedger:
    """
    Single entry point for ALL customer financial transactions.

    Args:
        type: "DEBIT" (customer owes more) or "CREDIT" (customer owes less)
        amount: Always positive. Sign is determined by type.
        reference_id: Order ID, payment ID, or cancellation reference
        description: Human-readable description for audit trail

    Returns:
        The created CustomerLedger entry

    Side effects:
        Updates customer.outstanding_balance by recomputing from full ledger.
        This guarantees outstanding_balance is always consistent with ledger.

    Never update customer.outstanding_balance directly — always use this function.
    """
    if amount <= 0:
        logger.warning(
            "record_transaction called with non-positive amount %.2f for customer %s — skipping",
            amount, customer_id
        )
        return None

    # 1. Add ledger entry
    entry = CustomerLedger(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        customer_id=customer_id,
        type=type,
        amount=amount,
        reference_id=reference_id,
        description=description,
        created_at=datetime.utcnow()
    )
    db.add(entry)
    db.flush()  # flush to include this entry in the recompute below

    # 2. Recompute outstanding_balance from full ledger.
    # This is the only correct way — never do outstanding_balance += amount.
    computed = db.query(
        func.coalesce(
            func.sum(
                case(
                    (CustomerLedger.type == "DEBIT", CustomerLedger.amount),
                    else_=-CustomerLedger.amount
                )
            ),
            0.0
        )
    ).filter(
        CustomerLedger.customer_id == customer_id,
        CustomerLedger.tenant_id == tenant_id
    ).scalar()

    customer = db.get(Customer, customer_id)
    if customer:
        customer.outstanding_balance = max(0.0, float(computed))
        logger.info(
            "Transaction recorded: %s ₹%.2f ref=%s → outstanding=₹%.2f",
            type, amount, reference_id, customer.outstanding_balance
        )

    return entry


def recompute_outstanding_balance(
    db: Session,
    tenant_id: uuid.UUID,
    customer_id: uuid.UUID
) -> float:
    """
    Recomputes and saves outstanding_balance from ledger.
    Use this for data repair or after bulk operations.
    """
    computed = db.query(
        func.coalesce(
            func.sum(
                case(
                    (CustomerLedger.type == "DEBIT", CustomerLedger.amount),
                    else_=-CustomerLedger.amount
                )
            ),
            0.0
        )
    ).filter(
        CustomerLedger.customer_id == customer_id,
        CustomerLedger.tenant_id == tenant_id
    ).scalar()

    balance = max(0.0, float(computed))
    customer = db.get(Customer, customer_id)
    if customer:
        customer.outstanding_balance = balance
    return balance
