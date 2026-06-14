import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db, tenant_context
from app.models.order import Order, OrderLineItem, OrderStateLedger
from app.models.product import Product

router = APIRouter(prefix="/orders", tags=["Orders"])

class StatusUpdatePayload(BaseModel):
    to_status: str

@router.put("/{order_id}/status", status_code=status.HTTP_200_OK)
def update_order_status(
    order_id: uuid.UUID,
    payload: StatusUpdatePayload,
    db: Session = Depends(get_db)
):
    """
    Transitions order status and enforces real-time stock validation and atomic deduction
    upon confirming the order.
    """
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(
            status_code=404,
            detail="Order not found"
        )

    # Set tenant isolation context
    tenant_context.set(order.tenant_id)

    try:
        # Fetch Child Line Items
        items = db.query(OrderLineItem).filter(OrderLineItem.order_id == order_id).all()

        if payload.to_status == "Confirmed":
            # Inventory Guardrail Validation Loop
            for item in items:
                # Resolve product variables dynamically
                prod_data = db.query(Product).filter(Product.id == item.product_id).first()
                if prod_data:
                    item.sku_code = prod_data.sku_id
                    item.product_name = prod_data.sku_id
                else:
                    item.sku_code = "UNKNOWN_SKU"
                    item.product_name = "Unknown Product"

                # Core inventory look up logic matching directives exactly
                product = db.query(Product).filter(Product.sku_id == item.sku_code).first()
                if product:
                    # Check if enough physical stock exists
                    if product.stock_quantity < item.quantity:
                        raise HTTPException(
                            status_code=400, 
                            detail=f"Insufficient stock for {item.product_name}. Requested: {item.quantity}, Available: {product.stock_quantity}"
                        )

            # Atomic Decrements: If all items pass, safely decrement stock counts
            for item in items:
                product = db.query(Product).filter(Product.sku_id == item.sku_code).first()
                if product:
                    product.stock_quantity -= item.quantity

        # Record state transition to OrderStateLedger
        current_status = order.current_status
        db.add(OrderStateLedger(
            tenant_id=order.tenant_id,
            order_id=order.id,
            from_status=current_status,
            to_status=payload.to_status,
            updated_by="system_orders_agent"
        ))

        db.commit()
        return {
            "status": "success",
            "order_id": str(order.id),
            "new_status": payload.to_status
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Status update transaction crash: {str(e)}"
        )
