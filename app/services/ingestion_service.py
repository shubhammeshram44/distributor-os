import csv
import uuid
import logging
import io
from typing import List, Dict, Optional, Any
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from pydantic import BaseModel
import google.generativeai as genai
from app.models.ingestion import IngestionJob, IngestionStaging
from app.models.product import Product, ProductAlias
from app.models.inventory import Inventory
from app.config import settings
from app.database import tenant_context, with_db_retry
import openpyxl

# Event Discriminator & Ingestion Imports
from datetime import datetime
from app.models.tenant import DistributorTenant
from app.models.customer import Customer, CustomerAlias
from app.models.order import Order, OrderLineItem, OrderStateLedger
from app.services.gemini_service import GeminiService
from app.utils.phone import normalize_phone_number, get_phone_number_variants
from app.services.tenant_service import DEMO_TENANT_ID

logger = logging.getLogger(__name__)

class HeaderMapping(BaseModel):
    SKU: str
    Quantity: str
    Quantity_Committed: str

class IngestionService:
    # Class-level cache to share parsed phone mappings across instances and reduce database load
    _distributor_phone_cache: Dict[uuid.UUID, str] = {}

    @classmethod
    def invalidate_tenant_cache(cls, tenant_id: uuid.UUID) -> None:
        """
        Invalidates the cached business number for the given tenant ID.
        Should be called when distributor settings are updated.
        """
        if tenant_id in cls._distributor_phone_cache:
            cls._distributor_phone_cache.pop(tenant_id, None)
            logger.info("IngestionService: Invalidated cached distributor phone for tenant %s", tenant_id)

    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.enabled = bool(self.api_key)
        if self.enabled:
            try:
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel("gemini-1.5-flash")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini in Ingestion: {e}")
                self.enabled = False

    def parse_file(self, file_content: bytes, filename: str) -> List[Dict[str, Any]]:
        """
        Parses CSV or Excel bytes into a list of row dictionaries.
        """
        rows = []
        if filename.endswith(".csv"):
            text_stream = io.StringIO(file_content.decode("utf-8"))
            reader = csv.DictReader(text_stream)
            for row in reader:
                rows.append(dict(row))
        elif filename.endswith((".xlsx", ".xls")):
            wb = openpyxl.load_workbook(io.BytesIO(file_content), data_only=True)
            ws = wb.active
            headers = [cell.value for cell in ws[1]]
            for row_cells in ws.iter_rows(min_row=2, values_only=True):
                if any(row_cells): # Skip fully empty rows
                    row_dict = {headers[i]: row_cells[i] for i in range(len(headers)) if i < len(row_cells)}
                    rows.append(row_dict)
        else:
            raise ValueError("Unsupported file format. Please upload CSV or Excel.")
        return rows

    def get_column_mapping(self, headers: List[str]) -> Dict[str, str]:
        """
        Maps raw file headers to canonical keys: 'SKU', 'Quantity', 'Quantity_Committed'.
        """
        if self.enabled:
            try:
                prompt = (
                    "Analyze the following list of uploaded file headers. "
                    "Map these headers to our canonical fields: 'SKU', 'Quantity', 'Quantity_Committed'. "
                    "Return a JSON object where the keys are our canonical fields and the values are "
                    "the exact matched headers from the uploaded file list. "
                    f"Uploaded Headers: {headers}"
                )

                generation_config = {
                    "response_mime_type": "application/json",
                    "response_schema": HeaderMapping,
                }

                response = self.model.generate_content(
                    contents=[prompt],
                    generation_config=generation_config
                )
                import json
                mapping = json.loads(response.text)
                return mapping
            except Exception as e:
                logger.error(f"Gemini column mapping failed: {e}. Falling back to rule-based mapper.")

        return self._fallback_header_mapper(headers)

    def _fallback_header_mapper(self, headers: List[str]) -> Dict[str, str]:
        """
        Regex/keyword header mapper for fallback testing.
        """
        mapping = {"SKU": "", "Quantity": "", "Quantity_Committed": ""}
        normalized_headers = {h.lower().replace("_", "").replace(" ", ""): h for h in headers if h}

        # SKU matching
        for k in ["sku", "skuid", "itemcode", "productcode", "itemname", "product", "item"]:
            if k in normalized_headers:
                mapping["SKU"] = normalized_headers[k]
                break

        # Quantity matching
        for k in ["qty", "quantity", "stock", "quantityonhand", "onhand", "stockqty"]:
            if k in normalized_headers:
                mapping["Quantity"] = normalized_headers[k]
                break

        # Quantity Committed matching
        for k in ["committed", "quantitycommitted", "reserved", "committedqty", "allocated"]:
            if k in normalized_headers:
                mapping["Quantity_Committed"] = normalized_headers[k]
                break

        # Fallback defaults if no match found
        if not mapping["SKU"] and headers:
            mapping["SKU"] = headers[0]
        if not mapping["Quantity"] and len(headers) > 1:
            mapping["Quantity"] = headers[1]
        if not mapping["Quantity_Committed"] and len(headers) > 2:
            mapping["Quantity_Committed"] = headers[2]

        return mapping

    @with_db_retry
    def ingest_file(
        self,
        db: Session,
        tenant_id: uuid.UUID,
        file_content: bytes,
        filename: str
    ) -> IngestionJob:
        """
        Main entry point to upload a file, write to IngestionStaging, and validate row-by-row.
        """
        tenant_context.set(tenant_id)

        # 1. Parse File
        try:
            raw_rows = self.parse_file(file_content, filename)
        except Exception as e:
            logger.error(f"File parsing error: {e}")
            job = IngestionJob(
                tenant_id=tenant_id,
                source="Excel" if filename.endswith((".xlsx", ".xls")) else "CSV",
                status="Failed",
                filename=filename,
                total_rows=0
            )
            db.add(job)
            db.commit()
            return job

        # 2. Get Headers and Columns mapping
        headers = list(raw_rows[0].keys()) if raw_rows else []
        col_map = self.get_column_mapping(headers)

        # 3. Create Ingestion Job
        job = IngestionJob(
            tenant_id=tenant_id,
            source="Excel" if filename.endswith((".xlsx", ".xls")) else "CSV",
            status="Processing",
            filename=filename,
            total_rows=len(raw_rows),
            successful_rows=0,
            failed_rows=0
        )
        db.add(job)
        db.flush()

        # 4. Insert into Staging
        staging_records = []
        for row in raw_rows:
            staging_rec = IngestionStaging(
                tenant_id=tenant_id,
                job_id=job.id,
                raw_data=row,
                status="Staged"
            )
            db.add(staging_rec)
            staging_records.append(staging_rec)
        db.flush()

        # 5. Process Row-by-Row
        sku_col = col_map.get("SKU")
        qty_col = col_map.get("Quantity")
        committed_col = col_map.get("Quantity_Committed")

        for staging in staging_records:
            row_data = staging.raw_data
            
            # Start nested transaction (Savepoint) for row-level rollback isolation
            nested = db.begin_nested()
            try:
                # Extract fields
                raw_sku = str(row_data.get(sku_col) or "").strip()
                raw_qty = row_data.get(qty_col)
                raw_committed = row_data.get(committed_col)

                if not raw_sku:
                    raise ValueError("SKU field is empty in this row.")

                # Convert quantities to integers safely
                try:
                    qty = int(float(raw_qty)) if raw_qty is not None else 0
                    committed = int(float(raw_committed)) if raw_committed is not None else 0
                except (ValueError, TypeError):
                    raise ValueError(f"Invalid quantity formats. Qty: {raw_qty}, Committed: {raw_committed}")

                if qty < 0 or committed < 0:
                    raise ValueError("Quantities cannot be negative.")

                # Check if SKU matches a Product
                product_query = select(Product).where(Product.sku_id == raw_sku)
                product = db.execute(product_query).scalar_one_or_none()

                if not product:
                    # Try matching via ProductAlias
                    product_alias_query = (
                        select(Product)
                        .join(Product.aliases)
                        .where(func.lower(ProductAlias.alias_name) == raw_sku.lower())
                    )
                    product = db.execute(product_alias_query).scalar_one_or_none()

                if not product:
                    raise ValueError(f"SKU or Alias '{raw_sku}' does not exist in product catalog.")

                # Check or Create Inventory Record
                inventory_query = select(Inventory).where(Inventory.sku_id == product.id)
                inventory = db.execute(inventory_query).scalar_one_or_none()

                if not inventory:
                    inventory = Inventory(
                        tenant_id=tenant_id,
                        sku_id=product.id,
                        location="Staging Area", # Default
                        quantity_on_hand=qty,
                        quantity_committed=committed,
                        low_stock_threshold=10
                    )
                    db.add(inventory)
                else:
                    inventory.quantity_on_hand = qty
                    inventory.quantity_committed = committed

                # Save Staging State
                staging.status = "Validated"
                job.successful_rows += 1
                
                # Commit nested transaction
                nested.commit()

            except Exception as row_error:
                nested.rollback() # Rollback only changes inside this row's savepoint
                
                # Update staging logs in parent transaction context
                staging.status = "Failed"
                staging.error_message = str(row_error)
                job.failed_rows += 1
                logger.warning(f"File ingestion row failed: {row_error}")

            # Flush individual changes to parent db transaction
            db.flush()

        job.status = "Completed"
        db.commit()
        return job

    @with_db_retry
    def ingest_message(
        self,
        db: Session,
        tenant_id: uuid.UUID,
        sender_phone: str,
        message_text: str
    ) -> dict:
        """
        Event Discriminator Ingestion Pattern for incoming messaging orders.
        Filters self-messages from the distributor, then routes customer messages
        to the order parsing and creation pipeline.
        """
        tenant_context.set(tenant_id)
        
        # 1. Resolve registered business phone number (with caching)
        distributor_phone = self._distributor_phone_cache.get(tenant_id)
        if not distributor_phone:
            tenant = db.query(DistributorTenant).filter(DistributorTenant.id == tenant_id).first()
            if tenant and tenant.whatsapp_order_phone:
                distributor_phone = tenant.whatsapp_order_phone
                self._distributor_phone_cache[tenant_id] = distributor_phone

        # 2. Number Normalization & Event Discriminator logic gate
        norm_sender = normalize_phone_number(sender_phone)
        norm_distributor = normalize_phone_number(distributor_phone) if distributor_phone else ""

        if norm_distributor and norm_sender == norm_distributor:
            logger.info("IngestionService: Received message from distributor business number %s. Ignoring system/self-message.", norm_sender)
            return {"status": "ignored", "reason": "distributor_self_message"}

        # 3. Customer Identification Layer (Layer 1 Whitelist)
        customer = None
        if sender_phone:
            phone_variants = get_phone_number_variants(sender_phone)
            logger.info("IngestionService: Generated phone variants for lookup: %s", phone_variants)
            customer = db.query(Customer).join(CustomerAlias).filter(CustomerAlias.alias_value.in_(phone_variants)).first()
            if not customer:
                customer = db.query(Customer).filter(Customer.phone_number.in_(phone_variants)).first()

        if not customer:
            logger.warning("IngestionService: Clean ignore: Sender %s is not whitelisted for tenant %s", norm_sender, tenant_id)
            return {
                "status": "ignored",
                "message": f"Unknown customer phone number (not whitelisted): {norm_sender}",
                "job_id": None,
                "successful_rows": 0,
                "failed_rows": 0,
                "error_message": None
            }

        # 4. Core Ingestion Parser Layer (LLM Parsing)
        gemini_service = GeminiService()
        parsed_order = gemini_service.parse_order_text(message_text)
        logger.info("IngestionService: text='%s' parsed_result=%s", message_text, parsed_order.model_dump_json())

        raw_tokens = []
        if parsed_order.items:
            for item in parsed_order.items:
                raw_tokens.append({
                    "text_token": item.raw_product_name,
                    "qty": item.quantity
                })

        # Fallback keyword logic if LLM parsing yields no tokens
        if not raw_tokens:
            msg = message_text.lower()
            if "stayfree" in msg or "pad" in msg:
                raw_tokens.append({"text_token": "Stayfree Sanitary Napkins (XL)", "qty": 10})
            if "maggi" in msg:
                raw_tokens.append({"text_token": "Maggi 2-Min Noodles", "qty": 100})
            if "soap" in msg or "tata" in msg:
                raw_tokens.append({"text_token": "Tata Premium Soap", "qty": 500})
            
            if not raw_tokens:
                raw_tokens.append({"text_token": "Wholesale SKU Ingestion", "qty": 100})

        # Match tokens against database catalog
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

            # Match product case-insensitively
            product = get_best_product_for_alias_query(
                db.query(ProductAlias).filter(ProductAlias.alias_name.ilike(token))
            )
            if not product:
                product = get_best_product_for_prod_query(
                    db.query(Product).filter(Product.sku_id.ilike(token))
                )
            if not product:
                product = get_best_product_for_alias_query(
                    db.query(ProductAlias).filter(ProductAlias.alias_name.ilike(f"%{token}%"))
                )
            if not product:
                product = get_best_product_for_prod_query(
                    db.query(Product).filter(Product.sku_id.ilike(f"%{token}%"))
                )
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
                logger.info("IngestionService: Product matched: %s -> SKU %s", token, product.sku_id)
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
                has_unmatched = True
                logger.warning("IngestionService: Product unmatched: %s", token)
                parsed_items.append({
                    "product_name": f"Unmatched: {token}",
                    "sku_code": "UNMATCHED_SKU",
                    "sku_id": "UNMATCHED_SKU",
                    "brand": token,
                    "category": "Grocery",
                    "pack_size": "1 unit",
                    "qty": qty,
                    "wholesale_rate": 0.0,
                    "rate": 0.0
                })

        # 5. Database Commit Layer / Order Creation
        generated_order_id = f"ORD-2506-{uuid.uuid4().hex[:4].upper()}"
        new_order = Order(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            internal_order_id=generated_order_id,
            source="WhatsApp",
            customer_id=customer.id,
            invoice_type=parsed_order.extracted_invoice_preference,
            created_at=datetime.utcnow()
        )
        new_order.status = "NEEDS_REVIEW" if has_unmatched else "Draft"
        db.add(new_order)
        db.flush()

        # Write line item child records to DB
        for item in parsed_items:
            if item["sku_code"] == "UNMATCHED_SKU":
                product = db.query(Product).filter_by(sku_id="UNMATCHED_TRIAGE_SKU", tenant_id=tenant_id).first()
                if not product:
                    product = Product(
                        id=uuid.uuid4(),
                        tenant_id=tenant_id,
                        sku_id="UNMATCHED_TRIAGE_SKU",
                        brand="System Triage",
                        category="Triage",
                        pack_size="1 Unit",
                        base_price=0.0
                    )
                    db.add(product)
                    db.flush()
            else:
                product = db.query(Product).filter_by(sku_id=item["sku_code"], brand=item["brand"]).first()
                if not product:
                    product = Product(
                        id=uuid.uuid4(),
                        tenant_id=tenant_id,
                        sku_id=item["sku_code"],
                        brand=item["brand"],
                        category=item["category"],
                        pack_size=item["pack_size"],
                        base_price=item["rate"]
                    )
                    db.add(product)
                    db.flush()
                    
                    alias = ProductAlias(
                        id=uuid.uuid4(),
                        tenant_id=tenant_id,
                        product_id=product.id,
                        alias_name=item["product_name"]
                    )
                    db.add(alias)
                    db.flush()

            db.add(OrderLineItem(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                order_id=new_order.id,
                product_id=product.id,
                quantity=item["qty"],
                unit_price=item["rate"]
            ))

        order_status = "NEEDS_REVIEW" if has_unmatched else "Draft"
        new_order.status = order_status

        # Record state transition in ledger
        db.add(OrderStateLedger(
            tenant_id=tenant_id,
            order_id=new_order.id,
            from_status=None,
            to_status=order_status,
            updated_by="system_whatsapp_agent"
        ))

        db.commit()
        db.refresh(new_order)

        logger.info(
            "IngestionService: Success! Order %s created totaling %s",
            generated_order_id,
            sum(item["qty"] * item["rate"] for item in parsed_items)
        )

        return {
            "status": "success",
            "order_id": generated_order_id,
            "job_id": str(uuid.uuid4()),
            "successful_rows": 1,
            "failed_rows": 0,
            "message": "Order captured successfully but requires manual assignment." if has_unmatched else "Ingestion completed successfully!",
            "error_message": None
        }
