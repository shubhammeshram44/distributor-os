import typing
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.customer import Customer, CustomerAlias
from app.models.product import Product, ProductAlias
from app.models.order import Order, OrderLineItem, OrderStateLedger
from app.services.gemini_service import GeminiService

router = APIRouter(prefix="/whatsapp", tags=["WhatsApp"])

# Static Tenant ID fallback
DEMO_TENANT_ID = uuid.UUID("d3b07384-d113-4956-a5d2-64be7357c11d")

class WebhookPayload(BaseModel):
    tenant_id: typing.Optional[uuid.UUID] = None
    phone_number: typing.Optional[str] = None
    sender_phone: typing.Optional[str] = None
    message_text: str

@router.post("/webhook")
def handle_whatsapp_webhook(
    payload: WebhookPayload,
    db: Session = Depends(get_db)
):
    try:
        # 1. Print the raw incoming message
        print("\n================== INCOMING RAW WHATSAPP MESSAGE ==================")
        print(f"Sender: {payload.sender_phone}")
        print(f"Message: {payload.message_text}")
        print("=====================================================================\n")

        # Normalize message text for scanning
        msg = payload.message_text.lower()
        resolved_tenant_id = payload.tenant_id or DEMO_TENANT_ID
        phone = payload.sender_phone or payload.phone_number or ""

        # 1. Dynamically parse customer attributes based on keywords or phone aliases
        customer = None
        if phone:
            customer = db.query(Customer).join(CustomerAlias).filter(CustomerAlias.alias_value == phone).first()

        if not customer:
            if "maruthi" in msg:
                customer_name = "Maruthi Stores"
            elif "kaveri" in msg:
                customer_name = "Kaveri Provision Store"
            else:
                customer_name = "Kaveri Provision Store" # Default fallback

            customer = db.query(Customer).filter_by(retailer_name=customer_name).first()
            if not customer:
                cust_id = "CUST-101" if customer_name == "Kaveri Provision Store" else "CUST-102"
                customer = db.query(Customer).filter_by(customer_id=cust_id).first()
                if not customer:
                    customer = Customer(
                        id=uuid.uuid4(),
                        tenant_id=resolved_tenant_id,
                        customer_id=cust_id,
                        retailer_name=customer_name,
                        address_text="Bengaluru",
                        gstin="29AAAAA1111A1Z1",
                        tax_group="GST-18",
                        payment_terms="0-15 Days"
                    )
                    db.add(customer)
                    db.flush()
        else:
            customer_name = customer.retailer_name

        # 2. Parse unstructured text using Gemini Service or fall back to keyword logic
        gemini_service = GeminiService()
        parsed_order = gemini_service.parse_order_text(payload.message_text)

        parsed_items = []
        if parsed_order.items:
            for item in parsed_order.items:
                p_name = item.raw_product_name
                qty = item.quantity
                
                # Determine properties based on product name mapping
                if "stayfree" in p_name.lower() or "pad" in p_name.lower():
                    rate = 1250.0
                    sku = "PROD-STAYFREE-XL"
                    brand = "Stayfree"
                    category = "Sanitary"
                    pack_size = "XL"
                elif "maggi" in p_name.lower():
                    rate = 450.0
                    sku = "PROD-ITC-MAGGI"
                    brand = "Nestle"
                    category = "Noodles"
                    pack_size = "70g"
                elif "soap" in p_name.lower() or "tata" in p_name.lower():
                    rate = 47.3
                    sku = "PROD-HUL-SOAP"
                    brand = "HUL"
                    category = "Soap"
                    pack_size = "100g"
                else:
                    rate = 189.0
                    sku = "PROD-GENERIC"
                    brand = "Generic"
                    category = "Grocery"
                    pack_size = "1 unit"
                
                parsed_items.append({
                    "product_name": p_name,
                    "sku_code": sku,
                    "brand": brand,
                    "category": category,
                    "pack_size": pack_size,
                    "qty": qty,
                    "rate": rate
                })

        # Fallback if no items parsed dynamically
        if not parsed_items:
            if "stayfree" in msg or "pad" in msg:
                parsed_items.append({
                    "product_name": "Stayfree Sanitary Napkins (XL)",
                    "sku_code": "PROD-STAYFREE-XL",
                    "brand": "Stayfree",
                    "category": "Sanitary",
                    "pack_size": "XL",
                    "qty": 10,
                    "rate": 1250.0
                })
            elif "maggi" in msg:
                parsed_items.append({
                    "product_name": "Maggi 2-Min Noodles",
                    "sku_code": "PROD-ITC-MAGGI",
                    "brand": "Nestle",
                    "category": "Noodles",
                    "pack_size": "70g",
                    "qty": 100,
                    "rate": 450.0
                })
            elif "soap" in msg or "tata" in msg:
                parsed_items.append({
                    "product_name": "Tata Premium Soap",
                    "sku_code": "PROD-HUL-SOAP",
                    "brand": "HUL",
                    "category": "Soap",
                    "pack_size": "100g",
                    "qty": 500,
                    "rate": 47.3
                })
            else:
                parsed_items.append({
                    "product_name": "Wholesale SKU Ingestion",
                    "sku_code": "PROD-GENERIC",
                    "brand": "Generic",
                    "category": "Grocery",
                    "pack_size": "1 unit",
                    "qty": 100,
                    "rate": 189.0
                })

        # 3. Create unique Parent Order ID string
        generated_order_id = f"ORD-2506-{uuid.uuid4().hex[:4].upper()}"

        # 4. Construct parent Order
        new_order = Order(
            id=uuid.uuid4(),
            tenant_id=resolved_tenant_id,
            internal_order_id=generated_order_id,
            source="WhatsApp",
            customer_id=customer.id
        )
        db.add(new_order)
        db.flush()

        # 5. Loop through and write line item child records to DB
        for item in parsed_items:
            # Resolve product
            product = db.query(Product).filter_by(sku_id=item["sku_code"]).first()
            if not product:
                product = Product(
                    id=uuid.uuid4(),
                    tenant_id=resolved_tenant_id,
                    sku_id=item["sku_code"],
                    brand=item["brand"],
                    category=item["category"],
                    pack_size=item["pack_size"],
                    base_price=item["rate"]
                )
                db.add(product)
                db.flush()
                
                # Add product alias as well
                alias = ProductAlias(
                    id=uuid.uuid4(),
                    tenant_id=resolved_tenant_id,
                    product_id=product.id,
                    alias_name=item["product_name"]
                )
                db.add(alias)
                db.flush()

            # Create OrderLineItem link
            db.add(OrderLineItem(
                id=uuid.uuid4(),
                tenant_id=resolved_tenant_id,
                order_id=new_order.id,
                product_id=product.id,
                quantity=item["qty"],
                unit_price=item["rate"]
            ))

        # Record state transition (maps to Pending status in Recent Orders UI)
        db.add(OrderStateLedger(
            tenant_id=resolved_tenant_id,
            order_id=new_order.id,
            from_status=None,
            to_status="Draft",
            updated_by="system_whatsapp_agent"
        ))

        # 2. Print the structured line items before committing
        print("\n================== GENERATED STRUCTURED DATA ==================")
        print(f"Assigned Customer: {customer_name}")
        print(f"Generated Order ID: {generated_order_id}")
        print(f"Parsed Items Array: {parsed_items}")
        print("=====================================================================\n")

        db.commit()
        db.refresh(new_order)

        # Aggregate total amount for logs
        total_amount = sum(item["qty"] * item["rate"] for item in parsed_items)
        print(f"Success! Persisted parsed text order for {customer_name} totaling {total_amount}")
        
        return {
            "status": "success",
            "order_id": generated_order_id,
            "job_id": str(uuid.uuid4()),
            "successful_rows": 1,
            "failed_rows": 0,
            "error_message": None
        }

    except Exception as e:
        db.rollback()
        print(f"Database Ingestion Failure: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database write crash: {str(e)}")
