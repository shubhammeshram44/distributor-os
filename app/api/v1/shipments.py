import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select, and_
from sqlalchemy.orm import Session, aliased
from app.database import get_db, tenant_context
from app.models.order import Order, OrderLineItem, OrderStateLedger
from app.models.customer import Customer
from app.models.shipment import Shipment
from app.models.invoice import Invoice
from app.models.user import User
from app.api.v1.dashboard import ensure_demo_data


router = APIRouter(prefix="/shipments", tags=["Shipments"])

class ShipmentCreatePayload(BaseModel):
    driver_id: uuid.UUID
    vehicle_number: str
    order_ids: list[uuid.UUID]


class ShipmentStatusPayload(BaseModel):
    status: str
    source: str = "back_office"

@router.get("/pending")
def get_pending_shipments(
    tenant_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    ensure_demo_data(db)
    tenant_context.set(tenant_id)

    # 1. Confirmed orders subquery
    ledger_alias = aliased(OrderStateLedger)
    confirmed_orders_sub = (
        select(OrderStateLedger.order_id)
        .where(
            and_(
                OrderStateLedger.tenant_id == tenant_id,
                OrderStateLedger.to_status == "Confirmed",
                OrderStateLedger.timestamp == (
                    select(func.max(ledger_alias.timestamp))
                    .where(
                        and_(
                            ledger_alias.tenant_id == tenant_id,
                            ledger_alias.order_id == OrderStateLedger.order_id
                        )
                    )
                    .scalar_subquery()
                )
            )
        )
    )

    # 2. Query shipments already made
    shipment_order_ids = select(Shipment.order_id).where(Shipment.tenant_id == tenant_id)

    # 3. Filter orders lacking shipments
    pending_orders = (
        db.query(Order)
        .filter(
            and_(
                Order.tenant_id == tenant_id,
                Order.id.in_(confirmed_orders_sub),
                Order.id.not_in(shipment_order_ids)
            )
        )
        .all()
    )

    results = []
    for o in pending_orders:
        customer = db.get(Customer, o.customer_id)
        cust_name = customer.retailer_name if customer else "Unknown Store"

        invoice = db.query(Invoice).filter(Invoice.order_id == o.id).first()
        if invoice:
            invoice_amount = float(invoice.total_amount)
        else:
            invoice_amount = db.query(func.sum(OrderLineItem.quantity * OrderLineItem.unit_price)).filter(OrderLineItem.order_id == o.id).scalar() or 0.0

        results.append({
            "order_id": str(o.id),
            "internal_order_id": o.internal_order_id,
            "customer_name": cust_name,
            "invoice_amount": float(invoice_amount)
        })

    return results

@router.get("/active")
def get_active_shipments(
    tenant_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    ensure_demo_data(db)
    tenant_context.set(tenant_id)

    shipments = db.query(Shipment).filter(Shipment.tenant_id == tenant_id).all()
    results = []
    for s in shipments:
        order = db.get(Order, s.order_id)
        if not order:
            continue

        customer = db.get(Customer, order.customer_id)
        cust_name = customer.retailer_name if customer else "Unknown Store"

        invoice = db.query(Invoice).filter(Invoice.order_id == order.id).first()
        if invoice:
            invoice_amount = float(invoice.total_amount)
            # Calculate payment status
            from app.models.payment import PaymentInvoiceLink
            allocated = db.query(func.sum(PaymentInvoiceLink.amount_allocated)).filter(PaymentInvoiceLink.invoice_id == invoice.id).scalar() or 0.0
            is_paid = allocated >= invoice.total_amount
        else:
            invoice_amount = db.query(func.sum(OrderLineItem.quantity * OrderLineItem.unit_price)).filter(OrderLineItem.order_id == order.id).scalar() or 0.0
            is_paid = False

        results.append({
            "shipment_id": str(s.id),
            "driver_name": s.carrier,
            "vehicle_number": s.tracking_id,
            "status": s.status,
            "order_id": str(order.id),
            "internal_order_id": order.internal_order_id,
            "customer_name": cust_name,
            "invoice_amount": float(invoice_amount),
            "is_paid": bool(is_paid)
        })

    # Seed initial test run for default demo tenant to make layout visual pop
    if not results and tenant_id == uuid.UUID("d3b07384-d113-4956-a5d2-64be7357c11d"):
        order = db.query(Order).filter(Order.internal_order_id == "ORD-2505-1482").first()
        if order:
            customer = db.get(Customer, order.customer_id)
            dest = customer.address_text if customer else "Bengaluru"
            new_shipment = Shipment(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                order_id=order.id,
                carrier="Ramesh Kumar",
                tracking_id="KA-01-MJ-9876",
                status="Out For Delivery",
                destination=dest
            )
            db.add(new_shipment)
            db.commit()
            return get_active_shipments(tenant_id, db)

    return results

@router.post("", status_code=status.HTTP_201_CREATED)
def create_shipment(
    payload: ShipmentCreatePayload,
    tenant_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    ensure_demo_data(db)
    tenant_context.set(tenant_id)

    driver = db.get(User, payload.driver_id)
    if not driver:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Specified driver does not exist in the staff registry"
        )
    driver_name = driver.full_name

    created_shipments = []
    for order_id in payload.order_ids:
        order = db.get(Order, order_id)
        if not order:
            continue

        customer = db.get(Customer, order.customer_id)
        dest = customer.address_text if customer else "Unknown"

        # Check if already has shipment
        existing = db.query(Shipment).filter(Shipment.order_id == order_id).first()
        if existing:
            continue

        new_shipment = Shipment(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            order_id=order_id,
            carrier=driver_name,
            tracking_id=payload.vehicle_number,
            status="Out For Delivery",
            destination=dest
        )
        db.add(new_shipment)


        # Transition order to Dispatched in ledger
        db.add(OrderStateLedger(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            order_id=order_id,
            from_status=order.current_status,
            to_status="Dispatched",
            updated_by="back_office"
        ))
        created_shipments.append(new_shipment)

    db.commit()
    return {"status": "success", "count": len(created_shipments)}

@router.patch("/{shipment_id}/status")
def update_shipment_status(
    shipment_id: uuid.UUID,
    payload: ShipmentStatusPayload,
    db: Session = Depends(get_db)
):
    shipment = db.get(Shipment, shipment_id)
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")

    tenant_context.set(shipment.tenant_id)
    shipment.status = payload.status

    # Log transition in order ledger without modifying outstanding payment balance
    order = db.get(Order, shipment.order_id)
    if order:
        db.add(OrderStateLedger(
            id=uuid.uuid4(),
            tenant_id=shipment.tenant_id,
            order_id=order.id,
            from_status=order.current_status,
            to_status=payload.status,
            updated_by=payload.source
        ))

    db.commit()
    return {
        "status": "success",
        "shipment_id": str(shipment.id),
        "new_status": shipment.status
    }
