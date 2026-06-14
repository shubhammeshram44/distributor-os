import uuid
import logging
from datetime import datetime
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.models.ingestion import IngestionJob, IngestionStaging
from app.models.customer import Customer, CustomerAlias
from app.models.product import Product, ProductAlias
from app.models.order import Order, OrderLineItem, OrderStateLedger
from app.services.gemini_service import GeminiService
from app.database import tenant_context

logger = logging.getLogger(__name__)

class WhatsAppService:
    def __init__(self):
        self.gemini_service = GeminiService()

    def process_whatsapp_message(
        self,
        db: Session,
        tenant_id: uuid.UUID,
        phone_number: str,
        message_text: str
    ) -> IngestionJob:
        """
        Receives an unstructured WhatsApp message, writes it to a staging job,
        processes it, and maps it to a canonical Order or logs errors.
        """
        # Set tenant isolation context
        tenant_context.set(tenant_id)

        # 1. Create Ingestion Job and Staging Record
        job = IngestionJob(
            tenant_id=tenant_id,
            source="WhatsApp",
            status="Processing",
            total_rows=1,
            successful_rows=0,
            failed_rows=0
        )
        db.add(job)
        db.flush() # Secure job.id

        staging_row = IngestionStaging(
            tenant_id=tenant_id,
            job_id=job.id,
            raw_data={"phone_number": phone_number, "message_text": message_text},
            status="Staged"
        )
        db.add(staging_row)
        db.flush()

        try:
            # 2. Match Customer Alias (Phone number)
            # Find customer with alias matching the phone number
            customer_query = (
                select(Customer)
                .join(CustomerAlias)
                .where(CustomerAlias.alias_value == phone_number)
            )
            customer = db.execute(customer_query).scalar_one_or_none()

            if not customer:
                error_msg = f"Unknown customer phone number: {phone_number}"
                staging_row.status = "Failed"
                staging_row.error_message = error_msg
                job.failed_rows = 1
                job.status = "Completed"
                db.commit()
                logger.warning(f"WhatsApp order failed: {error_msg}")
                return job

            # 3. Use LLM/Gemini to Parse unstructured text
            parsed_order = self.gemini_service.parse_order_text(message_text)
            if not parsed_order.items:
                error_msg = "Could not parse any items or quantities from message."
                staging_row.status = "Failed"
                staging_row.error_message = error_msg
                job.failed_rows = 1
                job.status = "Completed"
                db.commit()
                return job

            # 4. Match SKU Aliases and populate line items
            line_items_to_create = []
            unmapped_items = []

            for item in parsed_order.items:
                product_query = (
                    select(Product)
                    .join(ProductAlias)
                    .where(func.lower(ProductAlias.alias_name) == item.raw_product_name.lower())
                )
                product = db.execute(product_query).scalar_one_or_none()

                if product:
                    line_items_to_create.append({
                        "product_id": product.id,
                        "quantity": item.quantity,
                        "unit_price": product.base_price
                    })
                else:
                    unmapped_items.append(item.raw_product_name)

            # 5. Check if we had any unmapped SKUs
            if unmapped_items:
                error_msg = f"Unmapped product aliases: {', '.join(unmapped_items)}"
                staging_row.status = "Failed"
                staging_row.error_message = error_msg
                job.failed_rows = 1
                job.status = "Completed"
                db.commit()
                logger.warning(f"WhatsApp order failed: {error_msg}")
                return job

            # 6. Commit to Canonical Order tables (Success path)
            order = Order(
                tenant_id=tenant_id,
                internal_order_id=f"WA-{int(datetime.utcnow().timestamp())}",
                source="WhatsApp",
                customer_id=customer.id,
                created_at=datetime.utcnow()
            )
            db.add(order)
            db.flush()

            for item_data in line_items_to_create:
                line_item = OrderLineItem(
                    tenant_id=tenant_id,
                    order_id=order.id,
                    product_id=item_data["product_id"],
                    quantity=item_data["quantity"],
                    unit_price=item_data["unit_price"]
                )
                db.add(line_item)

            # Log State transition to Append-only Ledger
            ledger = OrderStateLedger(
                tenant_id=tenant_id,
                order_id=order.id,
                from_status=None,
                to_status="Draft",
                updated_by="system_whatsapp_agent",
                metadata_json={
                    "phone_number": phone_number,
                    "raw_message": message_text
                }
            )
            db.add(ledger)

            # Update Ingestion Staging status
            staging_row.status = "Validated"
            job.successful_rows = 1
            job.status = "Completed"

            db.commit()
            logger.info(f"WhatsApp order created successfully: Order ID {order.id}")
            return job

        except Exception as e:
            db.rollback()
            logger.error(f"Error processing WhatsApp message: {e}", exc_info=True)
            staging_row.status = "Failed"
            staging_row.error_message = f"Internal processing error: {str(e)}"
            job.failed_rows = 1
            job.status = "Completed"
            db.commit()
            return job
