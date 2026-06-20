import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db, tenant_context
from app.models.customer import Customer, CustomerAlias
from app.models.ledger import CustomerLedger

router = APIRouter(prefix="/customers", tags=["Customers"])

class CustomerUpdatePayload(BaseModel):
    credit_limit: float
    billing_terms: str

@router.patch("/{customer_id}", status_code=status.HTTP_200_OK)
def update_customer(
    customer_id: uuid.UUID,
    payload: CustomerUpdatePayload,
    db: Session = Depends(get_db)
):
    """
    Updates a customer's credit limit and billing terms dynamically.
    """
    customer = db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(
            status_code=404,
            detail="Customer not found"
        )
    
    tenant_context.set(customer.tenant_id)
    
    customer.credit_limit = payload.credit_limit
    customer.payment_terms = payload.billing_terms
    
    db.commit()
    return {
        "status": "success",
        "customer_id": str(customer.id),
        "credit_limit": float(customer.credit_limit),
        "billing_terms": customer.payment_terms
    }


class CustomerCreatePayload(BaseModel):
    store_name: str
    contact_number: str
    delivery_address: str
    credit_limit: float
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
    
    db.commit()

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
    db: Session = Depends(get_db)
):
    """
    Fetches real customer profiles synchronized strictly from active database rows,
    completely decoupled from historical demo-data generation overrides.
    """
    tenant_context.set(tenant_id)
    
    # CLEAN SELECT: Stripped out ensure_demo_data to prevent mock side effects
    records = db.query(Customer).filter(Customer.tenant_id == tenant_id).all()
    
    response_payload = []
    for customer in records:
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
            # Explicitly forwards the true column state fields to the UI layer
            "phone": customer.phone_number if customer.phone_number else "N/A"
        })
        
    return response_payload


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
