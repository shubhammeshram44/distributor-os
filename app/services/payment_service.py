import uuid
from sqlalchemy.orm import Session
from app.database import tenant_context
from app.models.payment import Payment
from app.models.customer import Customer
from app.models.ledger import CustomerLedger

def process_payment(
    db: Session,
    tenant_id: uuid.UUID,
    customer_id: uuid.UUID,
    amount: float,
    method: str,
    reference_number: str | None = None
) -> Payment:
    """
    Core handler to process a customer payment, update their outstanding balance,
    and log the transaction in the customer account ledger.
    """
    token = tenant_context.set(tenant_id)
    try:
        customer = db.get(Customer, customer_id)
        if not customer:
            raise ValueError("Customer not found")

        # 1. Insert Payment Record
        payment = Payment(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            customer_id=customer_id,
            amount=amount,
            method=method,
            reference_number=reference_number,
            status="COMPLETED"
        )
        db.add(payment)
        db.flush()

        # 2. Log Credit in CustomerLedger
        ledger_ref = reference_number or f"PAY-{str(payment.id)[:8].upper()}"
        ledger_entry = CustomerLedger(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            customer_id=customer_id,
            type="CREDIT",
            amount=amount,
            reference_id=ledger_ref
        )
        db.add(ledger_entry)

        # 3. Decrement Customer Outstanding Balance
        customer.outstanding_balance = float(customer.outstanding_balance) - amount

        db.commit()
        db.refresh(payment)
        return payment
    except Exception as e:
        db.rollback()
        raise e
    finally:
        # Prevent context leakage
        tenant_context.reset(token)
