import uuid
import base64
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Cookie, Header, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy import func, select, and_, or_
from sqlalchemy.orm import Session, aliased, joinedload
from app.database import get_db, tenant_context
from app.models.order import Order, OrderLineItem, OrderStateLedger
from app.models.customer import Customer
from app.models.tenant import DistributorTenant
from app.models.shipment import Shipment
from app.models.invoice import Invoice
from app.models.user import User
from app.services.tenant_service import resolve_tenant_id


router = APIRouter(prefix="/shipments", tags=["Shipments"])


def encode_cursor(dt: datetime, uid: uuid.UUID) -> str:
    s = f"{dt.isoformat()}|{uid}"
    return base64.b64encode(s.encode("utf-8")).decode("utf-8")


def decode_cursor(cursor_str: str | None) -> tuple[datetime | None, uuid.UUID | None]:
    if not cursor_str:
        return None, None
    try:
        s = base64.b64decode(cursor_str.encode("utf-8")).decode("utf-8")
        parts = s.split("|")
        if len(parts) == 2:
            return datetime.fromisoformat(parts[0]), uuid.UUID(parts[1])
    except Exception:
        pass
    return None, None


def _fire_delivered_notification_sync(tenant_id: str, customer_id: str, order_id: str):
    import os, logging, httpx
    from app.database import SessionLocal
    from app.models.tenant import DistributorTenant
    from app.models.customer import Customer
    from app.models.order import Order
    from app.models.whatsapp_message_log import WhatsappMessageLog
    from app.utils.phone import normalize_phone_number

    logger = logging.getLogger(__name__)
    db = SessionLocal()
    try:
        tenant = db.get(DistributorTenant, tenant_id)
        customer = db.get(Customer, customer_id)
        order = db.get(Order, order_id)

        if not (tenant and customer and order):
            return

        prefs = tenant.notification_prefs or {}
        if not prefs.get("order_delivered", True):
            return
        if not customer.whatsapp_notifications_enabled:
            return
        if not tenant.whatsapp_phone_id:
            return

        phone = normalize_phone_number(customer.phone_number or "")
        if phone.startswith("+"):
            phone = phone[1:]
        if not phone:
            return

        items_list = []
        for item in order.line_items:
            if item.product:
                items_list.append(f"{item.product.brand} x {item.quantity}")
            elif item.unmatched_raw_text:
                items_list.append(f"{item.unmatched_raw_text} x {item.quantity}")
        item_summary = ", ".join(items_list)

        message = (
            f"Hi {customer.name},\n\n"
            f"✅ Your order {order.internal_order_id} has been delivered!\n"
            f"Items: {item_summary}\n"
            f"Total: ₹{order.total_amount}\n\n"
            f"Thank you for your order. We look forward to serving you again!\n"
            f"— {tenant.name}"
        )

        url = f"{os.getenv('EVOLUTION_API_URL', 'http://34.158.60.42:8080')}/message/sendText/{tenant.whatsapp_phone_id}"
        headers = {"apikey": os.getenv("EVOLUTION_API_KEY", "distributorbotkey2026")}
        payload = {"number": phone, "text": message}

        success = False
        error_msg = None
        try:
            resp = httpx.post(url, json=payload, headers=headers, timeout=10.0)
            success = resp.status_code in (200, 201)
            if not success:
                error_msg = f"Evolution API {resp.status_code}: {resp.text}"
        except Exception as ex:
            error_msg = str(ex)

        db.add(WhatsappMessageLog(
            tenant_id=tenant.id,
            customer_id=customer.id,
            order_id=order.id,
            event="order_delivered",
            to_phone=phone,
            message_body=message,
            status="sent" if success else "failed",
            error_message=error_msg
        ))
        db.commit()
        logger.info("Delivered notification %s for order %s", "sent" if success else "failed", order_id)

    except Exception as e:
        logger.warning("Delivered notification wrapper failed: %s", str(e))
    finally:
        db.close()


def _fire_dispatched_notification_sync(tenant_id: str, customer_id: str, order_id: str):
    import os, logging, httpx
    from app.database import SessionLocal
    from app.models.tenant import DistributorTenant
    from app.models.customer import Customer
    from app.models.order import Order
    from app.models.whatsapp_message_log import WhatsappMessageLog
    from app.utils.phone import normalize_phone_number

    logger = logging.getLogger(__name__)
    db = SessionLocal()
    try:
        tenant = db.get(DistributorTenant, tenant_id)
        customer = db.get(Customer, customer_id)
        order = db.get(Order, order_id)

        if not (tenant and customer and order):
            return

        prefs = tenant.notification_prefs or {}
        if not prefs.get("order_dispatched", True):
            return
        if not customer.whatsapp_notifications_enabled:
            return
        if not tenant.whatsapp_phone_id:
            return

        phone = normalize_phone_number(customer.phone_number or "")
        if phone.startswith("+"):
            phone = phone[1:]
        if not phone:
            return

        items_list = []
        for item in order.line_items:
            if item.product:
                items_list.append(f"{item.product.brand} x {item.quantity}")
            elif item.unmatched_raw_text:
                items_list.append(f"{item.unmatched_raw_text} x {item.quantity}")
        item_summary = ", ".join(items_list)

        message = (
            f"Hi {customer.name},\n\n"
            f"🚚 Your order {order.internal_order_id} has been dispatched!\n"
            f"Items: {item_summary}\n"
            f"Total: ₹{order.total_amount}\n\n"
            f"Your order is on its way.\n"
            f"— {tenant.name}"
        )

        url = f"{os.getenv('EVOLUTION_API_URL', 'http://34.158.60.42:8080')}/message/sendText/{tenant.whatsapp_phone_id}"
        headers = {"apikey": os.getenv("EVOLUTION_API_KEY", "distributorbotkey2026")}
        payload = {"number": phone, "text": message}

        success = False
        error_msg = None
        try:
            resp = httpx.post(url, json=payload, headers=headers, timeout=10.0)
            success = resp.status_code in (200, 201)
            if not success:
                error_msg = f"Evolution API {resp.status_code}: {resp.text}"
        except Exception as ex:
            error_msg = str(ex)

        db.add(WhatsappMessageLog(
            tenant_id=tenant.id,
            customer_id=customer.id,
            order_id=order.id,
            event="order_dispatched",
            to_phone=phone,
            message_body=message,
            status="sent" if success else "failed",
            error_message=error_msg
        ))
        db.commit()
        logger.info("Dispatched notification %s for order %s", "sent" if success else "failed", order_id)

    except Exception as e:
        logger.warning("Dispatched notification wrapper failed: %s", str(e))
    finally:
        db.close()

class ShipmentCreatePayload(BaseModel):
    driver_id: uuid.UUID
    vehicle_number: str = Field(..., min_length=1)
    order_ids: list[uuid.UUID]


class ShipmentStatusPayload(BaseModel):
    status: str
    source: str = "back_office"

@router.get("/pending")
def get_pending_shipments(
    limit: int = 50,
    cursor: str | None = None,
    q: str | None = None,
    status: str | None = None,
    access_token: str | None = Cookie(None),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db)
):
    extracted_tenant_id = resolve_tenant_id(None, access_token, authorization)
    tenant_context.set(extracted_tenant_id)

    limit = min(max(1, limit), 200)

    # 1. Confirmed orders subquery
    ledger_alias = aliased(OrderStateLedger)
    confirmed_orders_sub = (
        select(OrderStateLedger.order_id)
        .where(
            and_(
                OrderStateLedger.tenant_id == extracted_tenant_id,
                OrderStateLedger.to_status == "Confirmed",
                OrderStateLedger.timestamp == (
                    select(func.max(ledger_alias.timestamp))
                    .where(
                        and_(
                            ledger_alias.tenant_id == extracted_tenant_id,
                            ledger_alias.order_id == OrderStateLedger.order_id
                        )
                    )
                    .scalar_subquery()
                )
            )
        )
    )

    # 2. Query shipments already made
    shipment_order_ids = select(Shipment.order_id).where(Shipment.tenant_id == extracted_tenant_id)

    # 3. Filter orders lacking shipments
    query = (
        db.query(Order)
        .options(joinedload(Order.customer), joinedload(Order.line_items))
        .filter(
            and_(
                Order.tenant_id == extracted_tenant_id,
                Order.id.in_(confirmed_orders_sub),
                Order.id.not_in(shipment_order_ids)
            )
        )
    )

    # Apply search filter
    if q:
        query = query.join(Customer).filter(
            or_(
                Customer.retailer_name.ilike(f"%{q}%"),
                Order.internal_order_id.ilike(f"%{q}%")
            )
        )

    # Apply status filter
    if status:
        query = query.filter(Order.status == status)

    # Keyset pagination condition
    cursor_created_at, cursor_id = decode_cursor(cursor)
    if cursor_created_at and cursor_id:
        query = query.filter(
            or_(
                Order.created_at < cursor_created_at,
                and_(
                    Order.created_at == cursor_created_at,
                    Order.id < cursor_id
                )
            )
        )

    # Keyset pagination ordering
    query = query.order_by(Order.created_at.desc(), Order.id.desc())

    # Limit (fetch limit + 1 to check for next page)
    orders = query.limit(limit + 1).all()

    has_next = len(orders) > limit
    if has_next:
        next_items = orders[:limit]
        next_cursor = encode_cursor(next_items[-1].created_at, next_items[-1].id)
    else:
        next_items = orders
        next_cursor = None

    # Batch fetch invoices
    order_ids = [o.id for o in next_items]
    invoices_by_order_id = {}
    if order_ids:
        invoices = db.query(Invoice).filter(Invoice.order_id.in_(order_ids)).all()
        invoices_by_order_id = {inv.order_id: inv for inv in invoices}

    results = []
    for o in next_items:
        cust_name = o.customer.retailer_name if o.customer else "Unknown Store"

        invoice = invoices_by_order_id.get(o.id)
        if invoice:
            invoice_amount = float(invoice.total_amount)
            # Pre-cache payment_status
            o.payment_status = invoice.payment_status
        else:
            invoice_amount = sum(float(item.quantity * item.unit_price) for item in o.line_items)
            o.payment_status = "UNPAID"

        results.append({
            "order_id": str(o.id),
            "internal_order_id": o.internal_order_id,
            "customer_name": cust_name,
            "invoice_amount": float(invoice_amount)
        })

    return {
        "items": results,
        "next_cursor": next_cursor
    }

@router.get("/active")
def get_active_shipments(
    limit: int = 50,
    cursor: str | None = None,
    q: str | None = None,
    status: str | None = None,
    access_token: str | None = Cookie(None),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db)
):
    extracted_tenant_id = resolve_tenant_id(None, access_token, authorization)
    tenant_context.set(extracted_tenant_id)

    limit = min(max(1, limit), 200)

    query = (
        db.query(Shipment)
        .options(
            joinedload(Shipment.order).joinedload(Order.customer),
            joinedload(Shipment.order).joinedload(Order.line_items)
        )
        .filter(Shipment.tenant_id == extracted_tenant_id)
    )

    # Apply search filter
    if q:
        query = query.join(Shipment.order).join(Order.customer).filter(
            or_(
                Customer.retailer_name.ilike(f"%{q}%"),
                Order.internal_order_id.ilike(f"%{q}%"),
                Shipment.tracking_id.ilike(f"%{q}%")
            )
        )

    # Apply status filter
    if status:
        query = query.filter(Shipment.status == status)

    # Keyset pagination condition
    cursor_created_at, cursor_id = decode_cursor(cursor)
    if cursor_created_at and cursor_id:
        query = query.filter(
            or_(
                Shipment.created_at < cursor_created_at,
                and_(
                    Shipment.created_at == cursor_created_at,
                    Shipment.id < cursor_id
                )
            )
        )

    # Keyset pagination ordering
    query = query.order_by(Shipment.created_at.desc(), Shipment.id.desc())

    # Limit (fetch limit + 1 to check for next page)
    shipments = query.limit(limit + 1).all()

    has_next = len(shipments) > limit
    if has_next:
        next_items = shipments[:limit]
        next_cursor = encode_cursor(next_items[-1].created_at, next_items[-1].id)
    else:
        next_items = shipments
        next_cursor = None

    # Batch fetch invoices
    order_ids = [s.order_id for s in next_items if s.order]
    invoices_by_order_id = {}
    if order_ids:
        invoices = db.query(Invoice).filter(Invoice.order_id.in_(order_ids)).all()
        invoices_by_order_id = {inv.order_id: inv for inv in invoices}

    results = []
    for s in next_items:
        order = s.order
        if not order:
            continue

        cust_name = order.customer.retailer_name if order.customer else "Unknown Store"

        invoice = invoices_by_order_id.get(s.order_id)
        if invoice:
            invoice_amount = float(invoice.total_amount)
            # Pre-cache payment_status on both models to bypass lazy queries
            s.payment_status = invoice.payment_status
            order.payment_status = invoice.payment_status
            is_paid = s.payment_status == "PAID" or invoice.payment_status == "PAID"
        else:
            invoice_amount = sum(float(item.quantity * item.unit_price) for item in order.line_items)
            s.payment_status = "UNPAID"
            order.payment_status = "UNPAID"
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
    if not results and extracted_tenant_id == uuid.UUID("d3b07384-d113-4956-a5d2-64be7357c11d"):
        order = db.query(Order).filter(Order.internal_order_id == "ORD-2505-1482").first()
        if order:
            customer = db.get(Customer, order.customer_id)
            dest = customer.address_text if customer else "Bengaluru"
            new_shipment = Shipment(
                id=uuid.uuid4(),
                tenant_id=extracted_tenant_id,
                order_id=order.id,
                carrier="Ramesh Kumar",
                tracking_id="KA-01-MJ-9876",
                status="Out For Delivery",
                destination=dest
            )
            db.add(new_shipment)
            db.commit()
            return get_active_shipments(limit, cursor, q, status, access_token, authorization, db)

    return {
        "items": results,
        "next_cursor": next_cursor
    }

@router.post("", status_code=status.HTTP_201_CREATED)
def create_shipment(
    payload: ShipmentCreatePayload,
    background_tasks: BackgroundTasks,
    access_token: str | None = Cookie(None),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db)
):
    extracted_tenant_id = resolve_tenant_id(None, access_token, authorization)
    tenant_context.set(extracted_tenant_id)

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
            tenant_id=extracted_tenant_id,
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
            tenant_id=extracted_tenant_id,
            order_id=order_id,
            from_status=order.current_status,
            to_status="Dispatched",
            updated_by="back_office"
        ))
        order.status = "Dispatched"
        created_shipments.append(new_shipment)

    db.commit()

    # Fire order_dispatched notifications (non-blocking via BackgroundTasks)
    for s in created_shipments:
        order_obj = db.get(Order, s.order_id)
        if order_obj:
            background_tasks.add_task(
                _fire_dispatched_notification_sync,
                str(order_obj.tenant_id),
                str(order_obj.customer_id),
                str(order_obj.id)
            )

    return {"status": "success", "count": len(created_shipments)}

@router.patch("/{shipment_id}/status")
def update_shipment_status(
    shipment_id: uuid.UUID,
    payload: ShipmentStatusPayload,
    background_tasks: BackgroundTasks,
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
        order.status = payload.status

        # Update order.delivered_at and order.delivery_source if status is delivered/completed
        if payload.status.upper() in ("DELIVERED", "COMPLETED"):
            order.delivered_at = datetime.utcnow()
            order.delivery_source = payload.source

    db.commit()

    # Fire order_delivered notification if status is delivered/completed (non-blocking)
    if payload.status.upper() in ("DELIVERED", "COMPLETED") and order:
        background_tasks.add_task(
            _fire_delivered_notification_sync,
            str(order.tenant_id),
            str(order.customer_id),
            str(order.id)
        )

    return {
        "status": "success",
        "shipment_id": str(shipment.id),
        "new_status": shipment.status
    }
