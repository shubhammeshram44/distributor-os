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

        raw_tokens = []
        if parsed_order.items:
            for item in parsed_order.items:
                raw_tokens.append({
                    "text_token": item.raw_product_name,
                    "qty": item.quantity
                })

        # Fallback multi-token detection if no items parsed dynamically
        if not raw_tokens:
            if "stayfree" in msg or "pad" in msg:
                raw_tokens.append({"text_token": "Stayfree Sanitary Napkins (XL)", "qty": 10})
            if "maggi" in msg:
                raw_tokens.append({"text_token": "Maggi 2-Min Noodles", "qty": 100})
            if "soap" in msg or "tata" in msg:
                raw_tokens.append({"text_token": "Tata Premium Soap", "qty": 500})
            
            # Fallback if absolutely no keywords matched
            if not raw_tokens:
                raw_tokens.append({"text_token": "Wholesale SKU Ingestion", "qty": 100})

        # 3. Match items against database catalog and populate parsed_items
        parsed_items = []
        has_unmatched = False

        # Helper to get the best product from alias query results, avoiding MOCK products if possible
        def get_best_product_for_alias_query(query):
            matches = query.all()
            if not matches:
                return None
            for am in matches:
                p = db.query(Product).filter_by(id=am.product_id).first()
                if p and "MOCK" not in p.sku_id:
                    return p
            return db.query(Product).filter_by(id=matches[0].product_id).first()

        # Helper to get the best product from product query results, avoiding MOCK products if possible
        def get_best_product_for_prod_query(query):
            matches = query.all()
            if not matches:
                return None
            for p in matches:
                if "MOCK" not in p.sku_id:
                    return p
            return matches[0]

        for token_entry in raw_tokens:
            token = token_entry["text_token"]
            qty = token_entry["qty"]

            # Try finding the product in the database using case-insensitive match
            # 1. Exact match on ProductAlias alias_name
            product = get_best_product_for_alias_query(
                db.query(ProductAlias).filter(ProductAlias.alias_name.ilike(token))
            )

            # 2. Exact match on Product sku_id
            if not product:
                product = get_best_product_for_prod_query(
                    db.query(Product).filter(Product.sku_id.ilike(token))
                )

            # 3. Partial match on ProductAlias
            if not product:
                product = get_best_product_for_alias_query(
                    db.query(ProductAlias).filter(ProductAlias.alias_name.ilike(f"%{token}%"))
                )

            # 4. Partial match on Product sku_id
            if not product:
                product = get_best_product_for_prod_query(
                    db.query(Product).filter(Product.sku_id.ilike(f"%{token}%"))
                )

            # 5. Reverse word overlap matching if still not found
            if not product:
                words = [w.strip() for w in token.split() if len(w.strip()) > 2]
                for w in words:
                    if w.lower() in ["and", "the", "for", "please", "send", "need", "urgent", "with", "immediately", "box", "pack", "packet"]:
                        continue
                    product = get_best_product_for_alias_query(
                        db.query(ProductAlias).filter(ProductAlias.alias_name.ilike(f"%{w}%"))
                    )
                    if product:
                        break

            if product:
                # Found State: Map parameters dynamically from the matching database row
                parsed_items.append({
                    "product_name": token,
                    "sku_code": product.sku_id,
                    "sku_id": product.sku_id,
                    "brand": product.brand,
                    "category": product.category,
                    "pack_size": product.pack_size,
                    "qty": qty,
                    "wholesale_rate": float(product.base_price),
                    "rate": float(product.base_price)
                })
            else:
                # Unmatched State: Assign parameters and flag unmatched
                has_unmatched = True
                parsed_items.append({
                    "product_name": f"Unmatched: {token}",
                    "sku_code": "UNMATCHED_SKU",
                    "sku_id": "UNMATCHED_SKU",
                    "brand": "Generic",
                    "category": "Grocery",
                    "pack_size": "1 unit",
                    "qty": qty,
                    "wholesale_rate": 0.0,
                    "rate": 0.0
                })

        # 3. Create unique Parent Order ID string
        generated_order_id = f"ORD-2506-{uuid.uuid4().hex[:4].upper()}"

        # 4. Construct parent Order
        new_order = Order(
            id=uuid.uuid4(),
            tenant_id=resolved_tenant_id,
            internal_order_id=generated_order_id,
            source="WhatsApp",
            customer_id=customer.id,
            created_at=datetime.utcnow()
        )
        new_order.status = "Needs Review" if has_unmatched else "Draft"
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

        # Parent State Conditionals
        order_status = "Needs Review" if has_unmatched else "Draft"
        new_order.status = order_status

        # Record state transition (maps to Pending status in Recent Orders UI)
        db.add(OrderStateLedger(
            tenant_id=resolved_tenant_id,
            order_id=new_order.id,
            from_status=None,
            to_status=order_status,
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
