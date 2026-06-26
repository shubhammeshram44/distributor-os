import csv
import codecs
import uuid
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.database import get_db, tenant_context
from app.models.product import Product, ProductAlias
from app.models.inventory import Inventory
from app.api.v1.dashboard import ensure_demo_data

router = APIRouter(prefix="/products", tags=["Products"])

class ProductCreate(BaseModel):
    sku_id: str = Field(..., min_length=1)
    brand: str = Field(..., min_length=1)
    category: str = Field(..., min_length=1)
    pack_size: str = Field(..., min_length=1)
    base_price: float = Field(..., ge=0.0)

@router.post("", status_code=status.HTTP_201_CREATED)
def create_product(
    payload: ProductCreate,
    tenant_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """
    Manually inserts a new product and creates default aliases.
    """
    tenant_context.set(tenant_id)
    
    # Check if SKU already exists
    existing = db.query(Product).filter(Product.sku_id == payload.sku_id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Product with SKU '{payload.sku_id}' already exists."
        )
        
    new_product = Product(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        sku_id=payload.sku_id,
        brand=payload.brand,
        category=payload.category,
        pack_size=payload.pack_size,
        base_price=payload.base_price,
        stock_quantity=100  # Default initial stock
    )
    db.add(new_product)
    db.flush()
    
    # Create default aliases
    alias_sku = ProductAlias(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        product_id=new_product.id,
        alias_name=payload.sku_id
    )
    db.add(alias_sku)
    
    friendly_name = f"{payload.brand} {payload.category}"
    alias_friendly = ProductAlias(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        product_id=new_product.id,
        alias_name=friendly_name
    )
    db.add(alias_friendly)
    
    db.commit()
    return {
        "status": "success",
        "product_id": str(new_product.id),
        "sku_id": new_product.sku_id
    }

class StockAdjustmentPayload(BaseModel):
    sku_id: str = Field(..., min_length=1)
    quantity_received: int = Field(..., gt=0)

@router.post("/adjust-stock", status_code=status.HTTP_200_OK)
def adjust_stock(
    payload: StockAdjustmentPayload,
    tenant_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """
    Increments the stock quantity for a specific product SKU.
    """
    tenant_context.set(tenant_id)
    
    product = db.query(Product).filter(Product.sku_id == payload.sku_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with SKU '{payload.sku_id}' not found."
        )
        
    product.stock_quantity += payload.quantity_received
    
    # Also update or create the Inventory table record for joined queries
    inv = db.query(Inventory).filter(Inventory.sku_id == product.id).first()
    if inv:
        inv.quantity_on_hand += payload.quantity_received
    else:
        inv = Inventory(
            tenant_id=tenant_id,
            sku_id=product.id,
            location="Aisle-A1",
            quantity_on_hand=product.stock_quantity,
            quantity_committed=0,
            low_stock_threshold=10
        )
        db.add(inv)

    db.commit()
    
    return {
        "status": "success",
        "id": str(product.id),
        "sku_id": product.sku_id,
        "sku": product.sku_id,
        "product_name": f"{product.brand} {product.category}",
        "stock_quantity": inv.quantity_on_hand if inv else product.stock_quantity,
        "new_stock": inv.quantity_on_hand if inv else product.stock_quantity
    }



@router.get("", status_code=status.HTTP_200_OK)
def get_products(
    tenant_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """
    Retrieves the complete product catalog for a given tenant.
    """
    ensure_demo_data(db, tenant_id)
    tenant_context.set(tenant_id)
    products = db.query(Product).filter(
        Product.tenant_id == tenant_id,
        Product.sku_id != "UNMATCHED_TRIAGE_SKU"
    ).all()
    return [
        {
            "id": str(p.id),
            "sku_id": p.sku_id,
            "brand": p.brand,
            "category": p.category,
            "pack_size": p.pack_size,
            "base_price": float(p.base_price),
            "stock_quantity": p.stock_quantity
        }
        for p in products
    ]

@router.get("/inventory", status_code=status.HTTP_200_OK)
def get_inventory_items(
    tenant_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """
    Retrieves inventory levels for all products under the tenant.
    """
    ensure_demo_data(db, tenant_id)
    tenant_context.set(tenant_id)
    items = db.query(Product, Inventory).outerjoin(Inventory, Product.id == Inventory.sku_id).filter(Product.tenant_id == tenant_id, Product.sku_id != "UNMATCHED_TRIAGE_SKU").all()
    return [
        {
            "id": str(p.id),
            "sku_id": p.sku_id,
            "sku": p.sku_id,
            "product_name": f"{p.brand} {p.category}",
            "stock_quantity": inv.quantity_on_hand if inv is not None else 0,
            "low_stock_threshold": inv.low_stock_threshold if inv is not None else 10
        }
        for p, inv in items
    ]


@router.post("/import", status_code=status.HTTP_200_OK)
def import_products_csv(
    tenant_id: uuid.UUID = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Ingests a CSV product catalog file, performing transactional database UPSERTs
    and creating default product aliases for newly inserted items.
    """
    # 1. CSV Header Guard rails
    if not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Only CSV files (.csv) are supported."
        )

    try:
        # Decode the file stream using UTF-8
        csv_generator = codecs.iterdecode(file.file, 'utf-8')
        reader = csv.DictReader(csv_generator)

        # Enforce tenant isolation context
        tenant_context.set(tenant_id)

        # Validate headers existence
        required_headers = ["sku_id", "brand", "category", "pack_size", "base_price"]
        headers = [h.strip() for h in (reader.fieldnames or [])]
        if not all(field in headers for field in required_headers):
            missing_fields = [field for field in required_headers if field not in headers]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"CSV is missing required headers: {', '.join(missing_fields)}"
            )

        # Initialize tracking lists and telemetry counters
        success_count = 0
        error_rows = []
        updated_skus = []
        inserted_skus = []

        print("\n================== PRODUCT CATALOG IMPORT STARTED ==================")
        print(f"File Name: {file.filename}")
        print(f"Tenant ID: {tenant_id}")
        print("=====================================================================\n")

        # Start a nested savepoint or handle transaction block
        for idx, row in enumerate(reader, start=2):
            try:
                # Sanitize inputs
                sku_id = (row.get("sku_id") or "").strip()
                brand = (row.get("brand") or "").strip()
                category = (row.get("category") or "").strip()
                pack_size = (row.get("pack_size") or "").strip()
                base_price_raw = (row.get("base_price") or "").strip()

                if not sku_id or not brand or not category or not pack_size or not base_price_raw:
                    raise ValueError("All fields (sku_id, brand, category, pack_size, base_price) must be present and non-empty.")

                try:
                    base_price = float(base_price_raw)
                except ValueError:
                    raise ValueError(f"Invalid price value: '{base_price_raw}'. Must be a number.")

                if base_price < 0:
                    raise ValueError("Base price cannot be negative.")

                # Core transactional lookup logic loop
                existing_product = db.query(Product).filter(Product.sku_id == sku_id).first()
                if existing_product:
                    # Update operation
                    existing_product.base_price = base_price
                    existing_product.brand = brand
                    existing_product.category = category
                    existing_product.pack_size = pack_size
                    updated_skus.append(sku_id)
                else:
                    # Insert operation
                    new_product = Product(
                        id=uuid.uuid4(),
                        tenant_id=tenant_id,
                        sku_id=sku_id,
                        brand=brand,
                        category=category,
                        pack_size=pack_size,
                        base_price=base_price
                    )
                    db.add(new_product)
                    db.flush()

                    # Concurrently inject default entries into the ProductAlias table
                    alias_sku = ProductAlias(
                        id=uuid.uuid4(),
                        tenant_id=tenant_id,
                        product_id=new_product.id,
                        alias_name=sku_id
                    )
                    db.add(alias_sku)

                    # Build a friendly brand-category or brand-sku name for alias mapping
                    friendly_name = f"{brand} {category}"
                    alias_friendly = ProductAlias(
                        id=uuid.uuid4(),
                        tenant_id=tenant_id,
                        product_id=new_product.id,
                        alias_name=friendly_name
                    )
                    db.add(alias_friendly)
                    db.flush()
                    inserted_skus.append(sku_id)

                success_count += 1
            except Exception as e:
                error_rows.append(f"Row {idx}: {str(e)}")

        # Print complete summary of the transaction
        print("\n================== PRODUCT CATALOG IMPORT COMPLETE ==================")
        print(f"Successfully Upserted: {success_count} rows")
        print(f"Newly Inserted SKUs ({len(inserted_skus)}): {inserted_skus}")
        print(f"Updated Existing SKUs ({len(updated_skus)}): {updated_skus}")
        if error_rows:
            print(f"Failed Rows ({len(error_rows)}): {error_rows}")
        print("=====================================================================\n")

        if error_rows:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"message": "Validation errors encountered during import.", "errors": error_rows}
            )

        db.commit()
        return {
            "status": "success",
            "successful_rows": success_count,
            "inserted_count": len(inserted_skus),
            "updated_count": len(updated_skus),
            "failed_rows": len(error_rows)
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ingestion database crash: {str(e)}"
        )
