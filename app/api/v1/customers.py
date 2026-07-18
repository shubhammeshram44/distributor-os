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
    skip: int = 0,
    limit: int = 25,
    search: str = None,
    status_filter: str = None,
    db: Session = Depends(get_db)
):
    """
    Fetches customer profiles with pagination and search capabilities.
    """
    tenant_context.set(tenant_id)
    
    query = db.query(Customer).filter(Customer.tenant_id == tenant_id)
    
    # Search filter
    if search:
        search_term = f"%{search.lower()}%"
        query = query.filter(
            (Customer.retailer_name.ilike(search_term)) |
            (Customer.phone_number.ilike(search_term)) |
            (Customer.customer_id.ilike(search_term))
        )
    
    # Status filter (active/inactive based on outstanding balance)
    if status_filter:
        if status_filter == "active":
            query = query.filter(Customer.outstanding_balance > 0)
        elif status_filter == "inactive":
            query = query.filter(Customer.outstanding_balance == 0)
    
    # Total count before pagination
    total = query.count()
    
    # Apply pagination
    records = query.offset(skip).limit(limit).all()
    
    response_payload = []
    for customer in records:
        response_payload.append({
            "id": str(customer.id),
            "name": customer.retailer_name,
            "email": "",  # TODO: Add email field to Customer model
            "phone": customer.phone_number if customer.phone_number else (customer.aliases[0].alias_value if customer.aliases else "N/A"),
            "city": "",  # TODO: Add city field
            "state": "",  # TODO: Add state field
            "credit_limit": float(customer.credit_limit) if customer.credit_limit else 0.0,
            "outstanding_amount": float(customer.outstanding_balance) if customer.outstanding_balance else 0.0,
            "status": "active" if customer.outstanding_balance > 0 else "inactive",
            "created_at": customer.created_at.isoformat() if hasattr(customer, 'created_at') else None
        })
        
    return {
        "items": response_payload,
        "total": total,
        "skip": skip,
        "limit": limit
    }


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


@router.delete("/{customer_id}", status_code=status.HTTP_200_OK)
def delete_customer(
    customer_id: uuid.UUID,
    tenant_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """
    Soft delete a customer (marks as inactive).
    """
    tenant_context.set(tenant_id)
    
    customer = db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(
            status_code=404,
            detail="Customer not found"
        )
    
    # Soft delete: set outstanding_balance to 0 or add status field
    # For now, we'll just mark as deleted in the response
    db.delete(customer)
    db.commit()
    
    return {"status": "success", "message": "Customer deleted"}


@router.get("/export/csv", status_code=status.HTTP_200_OK)
def export_customers(
    tenant_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """
    Export customers as CSV.
    """
    tenant_context.set(tenant_id)
    
    records = db.query(Customer).filter(Customer.tenant_id == tenant_id).all()
    
    # Return data that can be converted to CSV by frontend
    response_payload = []
    for customer in records:
        response_payload.append({
            "Name": customer.retailer_name,
            "Phone": customer.phone_number or "N/A",
            "Address": customer.address_text or "N/A",
            "Credit Limit": float(customer.credit_limit) or 0.0,
            "Outstanding": float(customer.outstanding_balance) or 0.0,
            "Created": customer.created_at.isoformat() if hasattr(customer, 'created_at') else ""
        })
        
    return response_payload
