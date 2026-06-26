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

logger = logging.getLogger(__name__)

class HeaderMapping(BaseModel):
    SKU: str
    Quantity: str
    Quantity_Committed: str

class IngestionService:
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
