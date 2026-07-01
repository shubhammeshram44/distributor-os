import uuid
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.database import tenant_context, with_db_retry
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

@with_db_retry
def reconcile_payments_and_invoices(db: Session, tenant_id: uuid.UUID, customer_id: uuid.UUID | None = None):
    """
    Event-driven centralized payment status reconciler.
    Ensures all Confirmed, Dispatched, and Delivered orders have an associated Invoice,
    re-allocates unallocated payment balances to open invoices using FIFO, and
    propagates the payment status to Order and Shipment models explicitly.
    """
    from app.models.order import Order
    from app.models.shipment import Shipment
    
    # 1. Ensure all Confirmed/Dispatched/Delivered orders have Invoices
    order_query = db.query(Order).filter(Order.tenant_id == tenant_id)
    if customer_id:
        order_query = order_query.filter(Order.customer_id == customer_id)
    orders = order_query.all()
    
    invoices_created = False
    for order in orders:
        if order.current_status in ["Confirmed", "Dispatched", "Delivered"]:
            invoice = db.query(Invoice).filter(Invoice.order_id == order.id).first()
            if not invoice:
                customer = db.get(Customer, order.customer_id)
                amount_sum = sum(float(item.quantity * item.unit_price) for item in order.line_items)
                
                invoice = Invoice(
                    tenant_id=tenant_id,
                    order_id=order.id,
                    gstin=customer.gstin if (customer and customer.gstin) else "29AAAAA1111A1Z1",
                    total_amount=amount_sum,
                    irn_status="Cleared",
                    qr_code_status="Generated",
                    customer_id=order.customer_id,
                    payment_status="UNPAID",
                    amount_paid=0.0,
                    created_at=order.created_at
                )
                db.add(invoice)
                invoices_created = True
                
    if invoices_created:
        db.flush()

    # 2. Find completed payments and allocate unallocated balances via FIFO
    payment_query = db.query(Payment).filter(
        Payment.tenant_id == tenant_id,
        Payment.status == "COMPLETED"
    )
    if customer_id:
        payment_query = payment_query.filter(Payment.customer_id == customer_id)
    payments = payment_query.all()
    
    for payment in payments:
        allocated_sum = db.query(func.sum(PaymentInvoiceLink.amount_allocated)).filter(
            PaymentInvoiceLink.payment_id == payment.id
        ).scalar() or 0.0
        
        unallocated_amount = float(payment.amount) - float(allocated_sum)
        if unallocated_amount > 0.01:
            allocate_payment_fifo(
                db=db,
                customer_id=payment.customer_id,
                payment_id=payment.id,
                total_amount=unallocated_amount,
                tenant_id=tenant_id
            )
            
    # 3. Cascading update: propagate payment_status from Invoice to Order and Shipment models
    invoice_query = db.query(Invoice).filter(Invoice.tenant_id == tenant_id)
    if customer_id:
        invoice_query = invoice_query.filter(Invoice.customer_id == customer_id)
    invoices = invoice_query.all()
    
    for invoice in invoices:
        order = db.get(Order, invoice.order_id)
        if order:
            order.payment_status = invoice.payment_status
            
            shipments = db.query(Shipment).filter(Shipment.order_id == order.id).all()
            for shipment in shipments:
                shipment.payment_status = invoice.payment_status

    db.commit()

@with_db_retry
def process_payment(
    db: Session,
    tenant_id: uuid.UUID,
    customer_id: uuid.UUID,
    amount: float,
    method: str,
    reference_number: str | None = None,
    preferred_invoice_id: uuid.UUID | None = None  # NEW
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
        
        db.flush()

        # ── PREFERRED INVOICE ALLOCATION ──
        amount_remaining = amount

        # If a preferred invoice is specified, pay it first
        if preferred_invoice_id:
            preferred_invoice = db.get(Invoice, preferred_invoice_id)
            if preferred_invoice and preferred_invoice.payment_status not in ("PAID",):
                invoice_total = float(preferred_invoice.total_amount)
                invoice_paid = float(preferred_invoice.amount_paid or 0)
                amount_due = invoice_total - invoice_paid
                if amount_due > 0:
                    allocated = min(amount_remaining, amount_due)
                    preferred_invoice.amount_paid = invoice_paid + allocated
                    preferred_invoice.payment_status = "PAID" if preferred_invoice.amount_paid >= invoice_total else "PARTIALLY_PAID"
                    amount_remaining -= allocated
                    db.add(PaymentInvoiceLink(
                        id=uuid.uuid4(),
                        tenant_id=tenant_id,
                        payment_id=payment.id,
                        invoice_id=preferred_invoice.id,
                        amount_allocated=allocated
                    ))

        # Apply remainder (or full amount if no preferred invoice) via FIFO
        if amount_remaining > 0:
            allocate_payment_fifo(
                db=db,
                customer_id=customer_id,
                payment_id=payment.id,
                total_amount=amount_remaining,
                tenant_id=tenant_id
            )

        db.refresh(payment)
        return payment
    except Exception as e:
        db.rollback()
        raise e
    finally:
        tenant_context.reset(token)
