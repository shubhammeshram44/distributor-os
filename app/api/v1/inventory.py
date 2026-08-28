import uuid
from fastapi import APIRouter, Depends, HTTPException, status, Cookie, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db, tenant_context
from app.models.tenant import DistributorTenant
from app.models.product import Product
from app.models.inventory import Inventory
from app.services.tenant_service import resolve_tenant_id

router = APIRouter(prefix="/inventory", tags=["Inventory"])

class InwardPayload(BaseModel):
    sku_id: str
    quantity_added: int
    warehouse_location: str

@router.post("/inward", status_code=200)
def inward_stock(
    payload: InwardPayload,
    tenant_id: uuid.UUID | None = None,
    access_token: str | None = Cookie(None),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db)
):
    # Fix for TENANT-4: previously resolved "the tenant" via
    # db.query(DistributorTenant).first() -- an arbitrary row, ignoring the
    # caller's actual identity. In a real multi-tenant deployment, every
    # tenant's stock-inward writes would silently land against whichever
    # tenant happened to be first in the table.
    tenant_id = resolve_tenant_id(tenant_id, access_token, authorization)
    tenant_context.set(tenant_id)

    # Look up product by sku_id
    product = db.query(Product).filter_by(sku_id=payload.sku_id).first()
    if not product:
        product = Product(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            sku_id=payload.sku_id,
            brand="Generic",
            category="Grocery",
            pack_size="1 unit",
            base_price=450.00
        )
        db.add(product)
        db.flush()

    # Look up or create Inventory record
    inventory = db.query(Inventory).filter_by(sku_id=product.id).first()
    if not inventory:
        inventory = Inventory(
            tenant_id=tenant_id,
            sku_id=product.id,
            location=payload.warehouse_location,
            quantity_on_hand=payload.quantity_added,
            quantity_committed=0,
            low_stock_threshold=10
        )
        db.add(inventory)
    else:
        inventory.quantity_on_hand += payload.quantity_added
        inventory.location = payload.warehouse_location

    db.commit()
    return {"status": "success"}

@router.get("/dashboard-grid", status_code=200)
def get_inventory_dashboard_grid(
    tenant_id: uuid.UUID | None = None,
    access_token: str | None = Cookie(None),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db)
):
    # Fix for TENANT-4: same arbitrary-first-tenant issue as inward_stock above.
    tenant_id = resolve_tenant_id(tenant_id, access_token, authorization)
    tenant_context.set(tenant_id)
    
    # Outer join products to inventory
    items = db.query(Product, Inventory).outerjoin(Inventory, Product.id == Inventory.sku_id).filter(Product.tenant_id == tenant_id).all()
    
    data = []
    for p, inv in items:
        data.append({
            "sku_code": p.sku_id,
            "sku_id": p.sku_id,
            "product_name": f"{p.brand} {p.category}",
            "physical_stock": inv.quantity_on_hand if inv is not None else 0,
            "low_stock_threshold": inv.low_stock_threshold if inv is not None else 10
        })
    return {"data": data}
