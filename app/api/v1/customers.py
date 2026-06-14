import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db, tenant_context
from app.models.customer import Customer, CustomerAlias

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
    Onboards a new B2B customer (retailer) and binds their contact phone number alias.
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
        outstanding_balance=0.0
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
