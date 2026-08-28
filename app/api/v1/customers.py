import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.database import get_db, tenant_context
from app.models.customer import Customer, CustomerAlias
from app.models.ledger import CustomerLedger
from app.models.payment import Payment

router = APIRouter(prefix="/customers", tags=["Customers"])

class CustomerUpdatePayload(BaseModel):
    # Fix for CUST-8: previously an unconstrained float -- only the
    # frontend enforced credit_limit >= 0. The API itself accepted
    # negative values, which would make check_credit_limit's
    # `combined > credit_limit` comparison always true, silently locking
    # the customer out of ordering entirely.
    credit_limit: float = Field(..., ge=0)
    billing_terms: str

@router.patch("/{customer_id}", status_code=status.HTTP_200_OK)
def update_customer(
    customer_id: uuid.UUID,
    payload: CustomerUpdatePayload,
    tenant_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """
    Updates a customer's credit limit and billing terms dynamically.
    """
    # Fix for CUST-2: unlike every other endpoint in this router, this one
    # previously fetched the customer by ID alone (no tenant_id param at
    # all) and only set tenant_context AFTER the fetch had already
    # succeeded -- so any caller who obtained a customer UUID (from another
    # tenant's own data, logs, etc.) could silently alter that customer's
    # credit limit/billing terms across tenant boundaries. Now requires and
    # verifies tenant_id up front, matching the convention already used by
    # onboard_customer/list_customers/etc. in this same file.
    tenant_context.set(tenant_id)
    customer = db.get(Customer, customer_id)
    if not customer or customer.tenant_id != tenant_id:
        raise HTTPException(
            status_code=404,
            detail="Customer not found"
        )
    
    customer.credit_limit = payload.credit_limit
    customer.payment_terms = payload.billing_terms
    
    db.commit()
    return {
        "status": "success",
        "customer_id": str(customer.id),
        "credit_limit": float(customer.credit_limit),
        "billing_terms": customer.payment_terms
    }


@router.delete("/{customer_id}", status_code=status.HTTP_200_OK)
def delete_customer(
    customer_id: uuid.UUID,
    tenant_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """
    Soft-deletes (archives) a customer -- never a hard DELETE. Fix for
    CUST-4: this is the intentional, spec-required way to remove a
    customer from active use (e.g. a store that closed down) while
    guaranteeing their historical orders/invoices/ledger entries remain
    fully intact and queryable (this endpoint never touches those rows;
    DB-1's ondelete="RESTRICT" on every customer_id FK also makes a real
    hard-delete structurally impossible for any customer with financial
    history). Idempotent: deleting an already-archived customer is a
    no-op success, not an error.
    """
    tenant_context.set(tenant_id)
    customer = db.get(Customer, customer_id)
    if not customer or customer.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Customer not found")

    if customer.is_active:
        customer.is_active = False
        customer.deleted_at = datetime.utcnow()
        db.commit()

    return {
        "status": "success",
        "customer_id": str(customer.id),
        "is_active": customer.is_active,
        "deleted_at": customer.deleted_at.isoformat() if customer.deleted_at else None
    }


@router.post("/{customer_id}/restore", status_code=status.HTTP_200_OK)
def restore_customer(
    customer_id: uuid.UUID,
    tenant_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """
    Reverses a soft-delete, restoring a customer to active use. Companion
    to delete_customer above -- since soft-delete is the only supported
    delete mechanism (CUST-4), restoring is just as important: an
    accidental archive must be undoable without any data-recovery effort,
    since no data was ever actually removed.
    """
    tenant_context.set(tenant_id)
    customer = db.get(Customer, customer_id)
    if not customer or customer.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Customer not found")

    if not customer.is_active:
        customer.is_active = True
        customer.deleted_at = None
        db.commit()

    return {"status": "success", "customer_id": str(customer.id), "is_active": customer.is_active}


class CustomerCreatePayload(BaseModel):
    store_name: str
    contact_number: str
    delivery_address: str
    # Fix for CUST-8: same unconstrained-credit_limit gap as
    # CustomerUpdatePayload above.
    credit_limit: float = Field(..., ge=0)
    billing_terms: str

@router.post("", status_code=status.HTTP_201_CREATED)
def onboard_customer(
    payload: CustomerCreatePayload,
    tenant_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """
    Onboards a new B2B customer (retailer), populates their main profile contact path,
    and binds their contact phone number alias safely for multi-tenant protection layers.
    """
    tenant_context.set(tenant_id)
    
    # Check if contact number alias already exists
    existing_alias = db.query(CustomerAlias).filter(CustomerAlias.alias_value == payload.contact_number).first()
    if existing_alias:
        raise HTTPException(
            status_code=400,
            detail=f"Customer with contact number '{payload.contact_number}' already registered."
        )

    customer_code = f"C-ONB-{int(datetime.utcnow().timestamp())}"

    new_cust = Customer(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        customer_id=customer_code,
        retailer_name=payload.store_name,
        address_text=payload.delivery_address,
        gstin="PENDING",
        tax_group="GST-18",
        payment_terms=payload.billing_terms,
        credit_limit=payload.credit_limit,
        outstanding_balance=0.0,
        phone_number=payload.contact_number
    )
    db.add(new_cust)
    db.flush()

    new_alias = CustomerAlias(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        customer_id=new_cust.id,
        alias_value=payload.contact_number
    )
    db.add(new_alias)

    # Fix for CUST-3: the existence check above is a plain check-then-insert
    # with no lock -- a classic TOCTOU race. Two near-simultaneous requests
    # for the same real-world customer could both pass that check before
    # either commits. The DB-level unique constraint on
    # customer_aliases(tenant_id, alias_value) is the actual backstop; catch
    # the resulting IntegrityError here and turn it into the same clean,
    # friendly 409 response instead of an unhandled 500.
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Customer with contact number '{payload.contact_number}' already registered."
        )

    return {
        "status": "success",
        "id": str(new_cust.id),
        "customer_id": new_cust.customer_id,
        "retailer_name": new_cust.retailer_name,
        "contact_number": new_alias.alias_value
    }


@router.get("", status_code=status.HTTP_200_OK)
def list_customers(
    tenant_id: uuid.UUID,
    skip: int = 0,
    limit: int = 50,
    search: str | None = None,
    sort_by: str = "retailer_name",
    sort_order: str = "asc",
    include_inactive: bool = False,
    db: Session = Depends(get_db)
):
    """
    Returns paginated customer profiles with optional search and sorting.
    """
    tenant_context.set(tenant_id)

    query = db.query(Customer).filter(Customer.tenant_id == tenant_id)
    # Fix for CUST-4: soft-deleted (archived) customers are excluded from
    # the default staff-facing list -- their historical orders/invoices
    # remain fully queryable elsewhere (statement/payments endpoints look
    # customers up by ID directly, not through this filtered list), but a
    # deactivated store shouldn't keep cluttering everyday customer lists
    # or remain selectable for new orders. include_inactive=True opts back
    # in for an admin "show archived customers" view.
    if not include_inactive:
        query = query.filter(Customer.is_active.is_(True))

    if search:
        term = f"%{search.lower()}%"
        # Fix for CUST-6: search previously only matched Customer.retailer_name
        # / Customer.phone_number -- a customer with an additional identity in
        # customer_aliases (e.g. a second WhatsApp number, which the ingestion
        # whitelist in ingestion_service.py DOES check via CustomerAlias) was
        # invisible to this staff-facing search even though the customer
        # genuinely exists. Join in matching aliases as an additional match path.
        alias_customer_ids = db.query(CustomerAlias.customer_id).filter(
            CustomerAlias.tenant_id == tenant_id,
            CustomerAlias.alias_value.ilike(term)
        ).subquery()
        query = query.filter(
            Customer.retailer_name.ilike(term) |
            Customer.phone_number.ilike(term) |
            Customer.id.in_(alias_customer_ids)
        )

    _sort_col = {
        "retailer_name": Customer.retailer_name,
        "outstanding_balance": Customer.outstanding_balance,
        "credit_limit": Customer.credit_limit,
    }.get(sort_by, Customer.retailer_name)
    # Fix for CUST-7: sorting by a non-unique column (retailer_name,
    # outstanding_balance, credit_limit -- the latter two often share a
    # common default value like 100000.0 across many customers) with only
    # .offset/.limit and no secondary tiebreaker can reorder/duplicate/skip
    # rows across pages whenever values tie, since SQL does not guarantee
    # stable ordering for ties without an explicit tiebreaker column.
    # Customer.id is unique, so appending it as a secondary sort key makes
    # pagination deterministic and stable across repeated requests.
    if sort_order == "desc":
        query = query.order_by(_sort_col.desc(), Customer.id.desc())
    else:
        query = query.order_by(_sort_col.asc(), Customer.id.asc())

    total_count = query.count()
    records = query.offset(skip).limit(limit).all()

    response_payload = []
    for customer in records:
        # Fix for CUST-7 (phone-fallback nondeterminism): customer.aliases
        # is an unordered lazy-loaded collection -- picking aliases[0]
        # directly could return a different alias between requests. Sort
        # by id for a stable, reproducible choice.
        fallback_alias = min(customer.aliases, key=lambda a: a.id) if customer.aliases else None
        response_payload.append({
            "id": str(customer.id),
            "customer_id": customer.customer_id,
            "retailer_name": customer.retailer_name,
            "address_text": customer.address_text if customer.address_text else "N/A",
            "gstin": customer.gstin if customer.gstin else "PENDING",
            "tax_group": customer.tax_group if customer.tax_group else "GST-18",
            "payment_terms": customer.payment_terms if customer.payment_terms else "Net 30",
            "credit_limit": float(customer.credit_limit) if customer.credit_limit else 0.0,
            "outstanding_balance": float(customer.outstanding_balance) if customer.outstanding_balance else 0.0,
            "phone": customer.phone_number if customer.phone_number else (fallback_alias.alias_value if fallback_alias else "N/A"),
            "whatsapp_notifications_enabled": customer.whatsapp_notifications_enabled,
            "is_active": customer.is_active,
            "deleted_at": customer.deleted_at.isoformat() if customer.deleted_at else None
        })

    return {"items": response_payload, "total": total_count, "skip": skip, "limit": limit}


@router.get("/{customer_id}/statement")
def get_customer_statement(
    customer_id: uuid.UUID,
    tenant_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    tenant_context.set(tenant_id)
    
    customer = db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )
        
    records = (
        db.query(CustomerLedger)
        .filter(CustomerLedger.customer_id == customer_id)
        .order_by(CustomerLedger.created_at.asc())
        .all()
    )
    
    statement = []
    running_balance = 0.0
    for r in records:
        if r.type == "DEBIT":
            running_balance += float(r.amount)
        elif r.type == "CREDIT":
            running_balance -= float(r.amount)
            
        statement.append({
            "id": str(r.id),
            "created_at": r.created_at.isoformat(),
            "type": r.type,
            "amount": float(r.amount),
            "reference_id": r.reference_id,
            "running_balance": running_balance
        })
        
    return {
        "customer_id": str(customer_id),
        "retailer_name": customer.retailer_name,
        "running_balance": running_balance,
        "statement": statement
    }


@router.get("/{customer_id}/payments", status_code=status.HTTP_200_OK)
def get_customer_payments(
    customer_id: uuid.UUID,
    tenant_id: uuid.UUID,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    Returns paginated payment history for a specific customer.
    """
    tenant_context.set(tenant_id)

    customer = db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    total_count = db.query(Payment).filter(
        Payment.customer_id == customer_id,
        Payment.tenant_id == tenant_id
    ).count()

    payments = (
        db.query(Payment)
        .filter(Payment.customer_id == customer_id, Payment.tenant_id == tenant_id)
        .order_by(Payment.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    items = [
        {
            "id": str(p.id),
            "payment_code": f"PAY-REC-{str(p.id)[:8].upper()}",
            "amount": float(p.amount),
            "method": p.method,
            "reference_number": p.reference_number,
            "status": p.status,
            "created_at": p.created_at.isoformat()
        }
        for p in payments
    ]

    return {
        "customer_id": str(customer_id),
        "retailer_name": customer.retailer_name,
        "items": items,
        "total": total_count,
        "skip": skip,
        "limit": limit
    }


@router.get("/{customer_id}/payment-promises", status_code=status.HTTP_200_OK)
def get_customer_payment_promises(
    customer_id: uuid.UUID,
    tenant_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """
    Returns a customer's payment-promise history (from inbound WhatsApp
    replies like "I'll pay by Friday") plus a simple fulfilment-rate summary,
    refreshing any pending promises whose promised_date has already passed.
    """
    tenant_context.set(tenant_id)

    customer = db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    from app.services.payment_promise_service import refresh_promise_fulfillment
    from app.models.payment_promise import PaymentPromise

    refresh_promise_fulfillment(db, tenant_id)

    promises = (
        db.query(PaymentPromise)
        .filter(PaymentPromise.customer_id == customer_id, PaymentPromise.tenant_id == tenant_id)
        .order_by(PaymentPromise.created_at.desc())
        .all()
    )

    items = [
        {
            "id": str(p.id),
            "promised_date": p.promised_date.isoformat(),
            "promised_amount": float(p.promised_amount) if p.promised_amount is not None else None,
            "raw_message": p.raw_message,
            "status": p.status,
            "created_at": p.created_at.isoformat(),
        }
        for p in promises
    ]

    resolved = [p for p in promises if p.status in ("fulfilled", "broken")]
    fulfilled_count = sum(1 for p in promises if p.status == "fulfilled")

    return {
        "customer_id": str(customer_id),
        "retailer_name": customer.retailer_name,
        "items": items,
        "total": len(items),
        "fulfilled_count": fulfilled_count,
        "resolved_count": len(resolved),
    }


class CustomerNotificationPrefPayload(BaseModel):
    whatsapp_notifications_enabled: bool

@router.patch("/{customer_id}/notification-prefs", status_code=status.HTTP_200_OK)
def update_customer_notification_prefs(
    customer_id: uuid.UUID,
    payload: CustomerNotificationPrefPayload,
    tenant_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    # Fix for CUST-2: same cross-tenant IDOR as update_customer above --
    # tenant_id is now required and verified up front.
    tenant_context.set(tenant_id)
    customer = db.get(Customer, customer_id)
    if not customer or customer.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )

    customer.whatsapp_notifications_enabled = payload.whatsapp_notifications_enabled
    db.commit()

    return {
        "status": "success",
        "customer_id": str(customer.id),
        "whatsapp_notifications_enabled": customer.whatsapp_notifications_enabled
    }


@router.get("/{customer_id}/recent-products", status_code=status.HTTP_200_OK)
def get_customer_recent_products(
    customer_id: uuid.UUID,
    tenant_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """
    Returns a unique list of products ordered by the customer in their last 5 orders.
    """
    tenant_context.set(tenant_id)

    customer = db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Get last 5 orders
    from app.models.order import Order, OrderLineItem
    from app.models.product import Product

    last_orders = (
        db.query(Order)
        .filter(Order.customer_id == customer_id, Order.tenant_id == tenant_id)
        .order_by(Order.created_at.desc())
        .limit(5)
        .all()
    )

    if not last_orders:
        return []

    order_ids = [order.id for order in last_orders]

    # Get line items for these orders
    line_items = (
        db.query(OrderLineItem)
        .filter(OrderLineItem.order_id.in_(order_ids), OrderLineItem.tenant_id == tenant_id)
        .all()
    )

    product_ids = list({li.product_id for li in line_items})
    if not product_ids:
        return []

    # Get unique products
    products = (
        db.query(Product)
        .filter(Product.id.in_(product_ids), Product.tenant_id == tenant_id)
        .all()
    )

    return [
        {
            "id": str(p.id),
            "brand": p.brand,
            "category": p.category,
            "pack_size": p.pack_size,
            "base_price": float(p.base_price or 0.0),
            "sku_id": p.sku_id
        }
        for p in products
    ]

