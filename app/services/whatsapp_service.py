import uuid
import logging
from sqlalchemy.orm import Session
from app.models.ingestion import IngestionJob, IngestionStaging
from app.services.ingestion_service import IngestionService
from app.utils.phone import normalize_phone_number
from app.database import tenant_context

logger = logging.getLogger(__name__)

class WhatsAppService:
    def __init__(self):
        self.ingestion_service = IngestionService()

    def process_whatsapp_message(
        self,
        db: Session,
        canonical_msg = None,
        tenant_id: uuid.UUID = None,
        phone_number: str = None,
        message_text: str = None
    ) -> IngestionJob:
        """
        Receives a WhatsApp message, creates an IngestionJob and IngestionStaging record,
        delegates logic to IngestionService.ingest_message, and updates status.
        """
        if canonical_msg is not None:
            tenant_id = canonical_msg.tenant_id
            phone_number = canonical_msg.sender_phone
            message_text = canonical_msg.message_text

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
        db.flush()  # Secure job.id

        staging_row = IngestionStaging(
            tenant_id=tenant_id,
            job_id=job.id,
            raw_data={"phone_number": phone_number, "message_text": message_text},
            status="Staged"
        )
        db.add(staging_row)
        db.flush()

        try:
            # 2. Delegate to IngestionService
            result = self.ingestion_service.ingest_message(
                db=db,
                tenant_id=tenant_id,
                sender_phone=phone_number,
                message_text=message_text
            )
            
            # 3. Update job and staging based on result
            if result.get("status") == "success":
                staging_row.status = "Validated"
                job.successful_rows = 1
                job.status = "Completed"
            elif result.get("status") == "ignored":
                if result.get("reason") == "distributor_self_message":
                    staging_row.status = "Ignored"
                    job.status = "Ignored"
                else:
                    staging_row.status = "Failed"
                    staging_row.error_message = result.get("message") or "Ignored"
                    job.failed_rows = 1
                    job.status = "Completed"
            else:
                staging_row.status = "Failed"
                staging_row.error_message = result.get("error_message") or "Unknown status"
                job.failed_rows = 1
                job.status = "Completed"
                
            db.commit()
            return job

        except Exception as e:
            db.rollback()
            logger.error("[WhatsAppService] Fatal exception processing message: %s", e, exc_info=True)
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
