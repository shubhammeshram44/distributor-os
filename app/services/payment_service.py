import uuid
from sqlalchemy.orm import Session
from app.database import tenant_context
from app.models.payment import Payment, PaymentInvoiceLink
from app.models.customer import Customer
from app.models.ledger import CustomerLedger
from app.models.invoice import Invoice

def allocate_payment_fifo(db: Session, customer_id: uuid.UUID, payment_id: uuid.UUID, total_amount: float, tenant_id: uuid.UUID):
    # 1. Fetch all unpaid or partially paid invoices for this customer, oldest first
    open_invoices = (
        db.query(Invoice)
        .filter(
            Invoice.customer_id == customer_id,
            Invoice.tenant_id == tenant_id,
            Invoice.payment_status.in_(["UNPAID", "PARTIALLY_PAID"])
        )
        .order_by(Invoice.created_at.asc())
        .all()
    )
    
    remaining_payment = total_amount
    
    for invoice in open_invoices:
        if remaining_payment <= 0:
            break
            
        # Calculate exactly how much is left to fully settle this specific invoice
        invoice_total = float(invoice.total_amount)
        invoice_paid = float(invoice.amount_paid or 0.0)
        amount_due = invoice_total - invoice_paid
        
        if amount_due <= 0:
            continue
            
        # Determine allocation slice for this specific invoice
        if remaining_payment >= amount_due:
            allocated_amount = amount_due
            invoice.amount_paid = invoice_total
            invoice.payment_status = "PAID"
            remaining_payment -= amount_due
        else:
            allocated_amount = remaining_payment
            invoice.amount_paid = invoice_paid + remaining_payment
            invoice.payment_status = "PARTIALLY_PAID"
            remaining_payment = 0.0
            
        # Save tracking trace record to the matching linking table
        link = PaymentInvoiceLink(
            id=uuid.uuid4(),
            payment_id=payment_id,
            invoice_id=invoice.id,
            amount_allocated=allocated_amount,
            tenant_id=tenant_id
        )
        db.add(link)

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

        # Allocate payment using FIFO logic down outstanding invoices
        allocate_payment_fifo(db, customer_id, payment.id, amount, tenant_id)

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
