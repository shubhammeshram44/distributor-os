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
from app.services.whatsapp_adapter import CanonicalWhatsAppMessage
from app.utils.phone import normalize_phone_number, get_phone_number_variants

logger = logging.getLogger(__name__)

class WhatsAppService:
    def __init__(self):
        self.gemini_service = GeminiService()

    def process_whatsapp_message(
        self,
        db: Session,
        canonical_msg: CanonicalWhatsAppMessage = None,
        tenant_id: uuid.UUID = None,
        phone_number: str = None,
        message_text: str = None
    ) -> IngestionJob:
        """
        Receives a WhatsApp message (either via CanonicalWhatsAppMessage model or 
        via raw individual parameters for backward compatibility), writes it to a staging job,
        processes it, and maps it to a canonical Order or logs errors.
        """
        if canonical_msg is not None:
            tenant_id = canonical_msg.tenant_id
            phone_number = canonical_msg.sender_phone
            message_text = canonical_msg.message_text
            corr_id = canonical_msg.correlation_id or f"corr-srv-{uuid.uuid4().hex[:8]}"
        else:
            corr_id = f"corr-srv-{uuid.uuid4().hex[:8]}"

        logger.info("[Ingestion Service - %s] Processing WhatsApp message", corr_id)

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
            # 2. Phone Number Normalization & Customer Alias Match
            normalized_phone = normalize_phone_number(phone_number)
            phone_variants = get_phone_number_variants(phone_number)
            logger.info("[Ingestion Service - %s] Normalized sender phone: %s -> %s, variants: %s", corr_id, phone_number, normalized_phone, phone_variants)

            customer_query = (
                select(Customer)
                .join(CustomerAlias)
                .where(CustomerAlias.alias_value.in_(phone_variants))
            )
            customer = db.execute(customer_query).scalar_one_or_none()

            if not customer:
                customer_query = (
                    select(Customer)
                    .where(Customer.phone_number.in_(phone_variants))
                )
                customer = db.execute(customer_query).scalar_one_or_none()

            if not customer:
                error_msg = f"Unknown customer phone number: {normalized_phone}"
                logger.warning("[Ingestion Service - %s] Customer resolution failed: %s", corr_id, error_msg)
                staging_row.status = "Failed"
                staging_row.error_message = error_msg
                job.failed_rows = 1
                job.status = "Completed"
                db.commit()
                return job

            logger.info("[Ingestion Service - %s] Customer matched: %s (ID: %s)", corr_id, customer.retailer_name, customer.id)

            # 3. LLM Parsing
            logger.info("[Ingestion Service - %s] Dispatching text to LLM parser", corr_id)
            parsed_order = self.gemini_service.parse_order_text(message_text)
            if not parsed_order.items:
                error_msg = "Could not parse any items or quantities from message."
                logger.warning("[Ingestion Service - %s] LLM parsing yielded no items: %s", corr_id, error_msg)
                staging_row.status = "Failed"
                staging_row.error_message = error_msg
                job.failed_rows = 1
                job.status = "Completed"
                db.commit()
                return job

            logger.info("[Ingestion Service - %s] Parsed items: %s", corr_id, parsed_order.items)

            # 4. Catalog Reconciliation
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
                    logger.info("[Ingestion Service - %s] Catalog matched: %s -> SKU %s", corr_id, item.raw_product_name, product.sku_id)
                    line_items_to_create.append({
                        "product_id": product.id,
                        "quantity": item.quantity,
                        "unit_price": product.base_price
                    })
                else:
                    logger.warning("[Ingestion Service - %s] Catalog unmatched: %s", corr_id, item.raw_product_name)
                    unmapped_items.append(item.raw_product_name)

            if unmapped_items:
                error_msg = f"Unmapped product aliases: {', '.join(unmapped_items)}"
                logger.warning("[Ingestion Service - %s] Ingestion aborted due to unmapped products", corr_id)
                staging_row.status = "Failed"
                staging_row.error_message = error_msg
                job.failed_rows = 1
                job.status = "Completed"
                db.commit()
                return job

            # 5. Order Creation & Ledger Persistence
            order = Order(
                tenant_id=tenant_id,
                internal_order_id=f"WA-{int(datetime.utcnow().timestamp())}",
                source="WhatsApp",
                customer_id=customer.id,
                invoice_type=parsed_order.extracted_invoice_preference,
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
                    "phone_number": normalized_phone,
                    "raw_message": message_text,
                    "correlation_id": corr_id
                }
            )
            db.add(ledger)

            # Update Ingestion Staging status
            staging_row.status = "Validated"
            job.successful_rows = 1
            job.status = "Completed"

            db.commit()
            logger.info("[Ingestion Service - %s] WhatsApp order created successfully: Order ID %s, internal_id: %s", corr_id, order.id, order.internal_order_id)
            return job

        except Exception as e:
            db.rollback()
            logger.error("[Ingestion Service - %s] Fatal exception processing message: %s", corr_id, e, exc_info=True)
            staging_row.status = "Failed"
            staging_row.error_message = f"Internal processing error: {str(e)}"
            job.failed_rows = 1
            job.status = "Completed"
            db.commit()
            return job

    def send_otp_message(self, mobile_number: str, otp_code: str) -> None:
        """
        Simulates sending a WhatsApp message containing the 6-digit OTP code.
        """
        normalized_num = normalize_phone_number(mobile_number)
        print(f"\n================== OUTGOING WHATSAPP OTP ==================")
        print(f"To: {normalized_num}")
        print(f"Message: Your verification code is: {otp_code}. Expires in 5 minutes.")
        print(f"===========================================================\n")
        logger.info(f"WhatsApp OTP sent to {normalized_num}: {otp_code}")
