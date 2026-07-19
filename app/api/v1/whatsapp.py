import typing
import uuid
import logging
import asyncio
import os
import sys
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks, Request
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.database import get_db, tenant_context, SessionLocal, with_db_retry
from app.models.user import User
from app.models.customer import Customer, CustomerAlias
from app.models.product import Product, ProductAlias
from app.models.order import Order, OrderLineItem, OrderStateLedger
from app.models.tenant import DistributorTenant
from app.services.gemini_service import GeminiService
from app.services.whatsapp_adapter import adapt_to_canonical, CanonicalWhatsAppMessage
from app.utils.phone import normalize_phone_number, get_phone_number_variants
from app.services.tenant_service import DEMO_TENANT_ID

router = APIRouter(prefix="/whatsapp", tags=["WhatsApp"])

logger = logging.getLogger("uvicorn.error")

# Bounded in-memory set to deduplicate Evolution API retries within a session.
# Keys are the Evolution API message IDs (data.key.id from the raw payload).
_PROCESSED_MSG_IDS: set[str] = set()
_PROCESSED_MSG_IDS_MAX = 10_000


def _check_and_mark_msg_id(msg_id: str) -> bool:
    """Return True if this message was already processed (duplicate)."""
    if msg_id in _PROCESSED_MSG_IDS:
        return True
    if len(_PROCESSED_MSG_IDS) >= _PROCESSED_MSG_IDS_MAX:
        _PROCESSED_MSG_IDS.pop()
    _PROCESSED_MSG_IDS.add(msg_id)
    return False


# Module-level singleton: GeminiService is expensive to initialise (configures API key, loads model).
_gemini_service_instance: GeminiService | None = None

def _get_gemini_service() -> GeminiService:
    global _gemini_service_instance
    if _gemini_service_instance is None:
        _gemini_service_instance = GeminiService()
    return _gemini_service_instance

class WebhookPayload(BaseModel):
    model_config = {"extra": "allow"}

    tenant_id: typing.Optional[uuid.UUID] = None
    phone_number: typing.Optional[str] = None
    sender_phone: typing.Optional[str] = None
    sender: typing.Optional[str] = None  # Fallback for regression firewall test
    receiver: typing.Optional[str] = None  # Operational phone number (B)
    message_text: typing.Optional[str] = None
    message: typing.Optional[str] = None  # Fallback for regression firewall test


# LEGACY_META_CODE_START
@router.get("/webhook")
def verify_whatsapp_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge")
):
    """
    WhatsApp Webhook Verification (GET handshake).
    """
    logger.warning("Meta Webhook GET verification invoked but Meta Integration is disabled.")
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Meta integration is disabled/legacy. Use Evolution API instead."
    )
# LEGACY_META_CODE_END


@with_db_retry
def process_whatsapp_webhook_payload(
    payload: WebhookPayload,
    db: Session,
    correlation_id: str
) -> dict:
    logger.info("[Ingestion - %s] Processing webhook payload using Event Discriminator", correlation_id)
    try:
        # 1. Payload Adaptation Layer: transform incoming payload to Canonical internal model
        try:
            canonical_msg = adapt_to_canonical(payload)
            if not canonical_msg.sender_phone:
                logger.warning("[Ingestion - %s] Failed to resolve contact or empty sender. Dropping and returning early.", correlation_id)
                return {"status": "ignored", "reason": "failed_sender_resolution"}
        except ValueError as ve:
            if str(ve) == "distributor_self_message":
                logger.info("[Ingestion - %s] Silently dropping distributor self-message (fromMe is True)", correlation_id)
                return {"status": "ignored", "reason": "distributor_self_message"}
            if str(ve) == "non_customer_chat":
                return {"status": "ignored", "reason": "non_customer_chat"}
            raise
        canonical_msg.correlation_id = correlation_id
        logger.info(
            "[Ingestion - %s] Payload adapted to Canonical Model: sender=%s, receiver=%s, text_length=%d",
            correlation_id,
            canonical_msg.sender_phone,
            canonical_msg.receiver_phone,
            len(canonical_msg.message_text)
        )

        msg_text = canonical_msg.message_text
        phone = canonical_msg.sender_phone
        receiver_phone = canonical_msg.receiver_phone

        # 1. Log the raw incoming message
        logger.info(
            "[Ingestion - %s] Incoming message: sender=%s, text_length=%d",
            correlation_id, phone, len(msg_text)
        )

        # 2. Tenant Resolution Layer
        bot_phone_id = None
        # LEGACY_META_CODE_START
        # extra = getattr(payload, "model_extra", None) or {}
        # entry = extra.get("entry")
        # if not entry and isinstance(payload, dict):
        #     entry = payload.get("entry")
        # 
        # if entry and isinstance(entry, list) and len(entry) > 0:
        #     changes = entry[0].get("changes", [])
        #     if changes and isinstance(changes, list) and len(changes) > 0:
        #         value = changes[0].get("value", {})
        #         if value and isinstance(value, dict):
        #             msg_metadata = value.get("metadata", {})
        #             bot_phone_id = msg_metadata.get("phone_number_id")
        # LEGACY_META_CODE_END

        # Resolve instance name as bot_phone_id from model_extra for Evolution API
        if not bot_phone_id:
            extra_fields = getattr(payload, "model_extra", None) or {}
            if not extra_fields and isinstance(payload, dict):
                extra_fields = payload
            if extra_fields:
                bot_phone_id = extra_fields.get("instance") or extra_fields.get("instanceId") or extra_fields.get("instanceName")

        resolved_tenant_id = None
        if bot_phone_id:
            tenant = db.query(DistributorTenant).filter(DistributorTenant.whatsapp_phone_id == bot_phone_id).first()
            if tenant:
                resolved_tenant_id = tenant.id
            else:
                if canonical_msg.tenant_id:
                    resolved_tenant_id = canonical_msg.tenant_id
                else:
                    logger.warning("[Ingestion - %s] Webhook message dropped: No tenant found with whatsapp_phone_id=%s", correlation_id, bot_phone_id)
                    return {
                        "status": "ignored",
                        "message": f"No tenant found for phone_number_id: {bot_phone_id}",
                        "job_id": None,
                        "successful_rows": 0,
                        "failed_rows": 0,
                        "error_message": None
                    }
        else:
            # Query the database to find the matching User record and retrieve their multi-tenant tenant_id
            clean_phone = phone
            if clean_phone and "@" in clean_phone:
                clean_phone = clean_phone.split("@")[0]
            normalized_phone = normalize_phone_number(clean_phone)
            phone_variants = get_phone_number_variants(clean_phone)
            user = db.query(User).filter(
                (User.phone_number == clean_phone) |
                (User.phone_number == normalized_phone) |
                (User.phone_number.in_(phone_variants)) |
                (User.email_or_phone == clean_phone) |
                (User.email_or_phone == normalized_phone) |
                (User.email_or_phone.in_(phone_variants))
            ).first()
            if user:
                resolved_tenant_id = user.tenant_id
                logger.info("[Ingestion - %s] Resolved tenant ID via matching User record: %s", correlation_id, resolved_tenant_id)
            
            if not resolved_tenant_id:
                resolved_tenant_id = canonical_msg.tenant_id
                if not resolved_tenant_id and receiver_phone:
                    tenant = db.query(DistributorTenant).filter(DistributorTenant.whatsapp_order_phone == receiver_phone).first()
                    if tenant:
                        resolved_tenant_id = tenant.id

            if not resolved_tenant_id:
                resolved_tenant_id = DEMO_TENANT_ID

        logger.info("[Ingestion - %s] Resolved active Tenant ID: %s", correlation_id, resolved_tenant_id)
        tenant_context.set(resolved_tenant_id)

        # Delegate to IngestionService.ingest_message
        from app.services.ingestion_service import IngestionService
        service = IngestionService()
        result = service.ingest_message(
            db=db,
            tenant_id=resolved_tenant_id,
            sender_phone=phone,
            message_text=msg_text
        )
        return result

    except Exception as e:
        db.rollback()
        logger.error("[Ingestion - %s] Database write crash: %s", correlation_id, str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database write crash: {str(e)}")


@router.post("/webhook")
async def handle_whatsapp_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    correlation_id = f"corr-{uuid.uuid4().hex[:8]}"
    try:
        payload_data = await request.json()
    except Exception as e:
        logger.error("[Ingestion - %s] Failed to parse request JSON: %s", correlation_id, str(e))
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
        
    event_type = payload_data.get("event")
    if event_type == "connection.update":
        data = payload_data.get("data") or {}
        state = data.get("state")
        instance_name = payload_data.get("instance")
        
        if state == "open" and instance_name:
            logger.info("Auto-syncing distributor phone on connection open for instance %s", instance_name)
            try:
                url = "http://34.158.60.42:8080/instance/fetchInstances"
                headers = {"apikey": "distributorbotkey2026"}
                
                import httpx
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(url, headers=headers)
                
                if response.status_code == 200:
                    instances_data = response.json()
                    instances_list = []
                    if isinstance(instances_data, list):
                        instances_list = instances_data
                    elif isinstance(instances_data, dict):
                        instances_list = instances_data.get("instances") or [instances_data]
                    
                    owner_jid = None
                    for inst in instances_list:
                        if isinstance(inst, dict) and inst.get("instanceName") == instance_name:
                            owner_jid = inst.get("ownerJid")
                            break
                    if not owner_jid and instances_list and isinstance(instances_list[0], dict):
                        owner_jid = instances_list[0].get("ownerJid")
                        
                    if owner_jid:
                        owner_phone = str(owner_jid)
                        if owner_phone.endswith("@s.whatsapp.net"):
                            owner_phone = owner_phone[:-15]
                        else:
                            owner_phone = owner_phone.split("@")[0]
                            
                        # Use a new DB session for this — do not reuse the webhook session.
                        new_db = SessionLocal()
                        try:
                            # Normalize to E.164 formatting
                            from app.utils.phone import normalize_phone_number
                            normalized_phone = normalize_phone_number(owner_phone)
                            
                            # STRICT LOOKUP: instance name is the definitive tenant identifier
                            # Never use owner_phone to find a tenant — only use it to UPDATE the found tenant
                            tenant = new_db.query(DistributorTenant).filter(
                                DistributorTenant.whatsapp_phone_id == instance_name
                            ).first()
                            if not tenant and hasattr(DistributorTenant, "whatsapp_instance_name"):
                                tenant = new_db.query(DistributorTenant).filter(getattr(DistributorTenant, "whatsapp_instance_name") == instance_name).first()

                            # Fallback: derive tenant from instance name prefix (dist-{tenant_id[:8]})
                            if not tenant and instance_name:
                                import re
                                from sqlalchemy import cast, String
                                id_match = re.search(r"([0-9a-f]{8})$", instance_name)
                                if id_match:
                                    short_id = id_match.group(1)
                                    tenant = new_db.query(DistributorTenant).filter(
                                        cast(DistributorTenant.id, String).like(f"{short_id}%")
                                    ).first()

                            # If tenant not found by instance name — STOP. Never use owner_phone to find tenant.
                            # owner_phone is only used to UPDATE the tenant's stored phone number below.
                            if not tenant:
                                logger.warning(
                                    "connection.update: no tenant found for instance %s — ignoring webhook",
                                    instance_name
                                )
                                return

                            normalized_owner = normalize_phone_number(owner_phone) if owner_phone else None
                            
                            if normalized_owner:
                                # Check if this phone belongs to a different tenant
                                other = new_db.query(DistributorTenant).filter(
                                    DistributorTenant.whatsapp_order_phone == normalized_owner,
                                    DistributorTenant.id != tenant.id
                                ).first()
                                
                                if other:
                                    logger.warning(
                                        "Phone %s belongs to tenant %s — NOT updating tenant %s",
                                        normalized_owner, other.id, tenant.id
                                    )
                                else:
                                    # Safe to update — phone belongs to this tenant or is new
                                    tenant.whatsapp_order_phone = normalized_owner
                                    logger.info(
                                        "Updated phone for tenant %s: %s",
                                        tenant.id, normalized_owner
                                    )
                            
                            tenant.whatsapp_phone_id = instance_name
                            tenant.whatsapp_connection_status = "connected"
                            tenant.whatsapp_disconnected_at = None
                            tenant.whatsapp_disconnect_reason = None
                            tenant.whatsapp_disconnect_notified = False
                            new_db.commit()
                            logger.info(
                                "Auto-synced: instance=%s phone=%s tenant=%s",
                                instance_name, normalized_owner, tenant.id
                            )
                            from app.services.ingestion_service import IngestionService
                            IngestionService.invalidate_tenant_cache(tenant.id)
                            try:
                                from app.services.gateway_service import EvolutionGatewayService
                                service = EvolutionGatewayService()
                                await service.configure_webhook(instance_name)
                                logger.info("Successfully re-configured webhook for instance %s on connection open", instance_name)
                            except Exception as webhook_exc:
                                logger.error("Failed to re-configure webhook for instance %s on connection open: %s", instance_name, str(webhook_exc))
                        except Exception as db_exc:
                            new_db.rollback()
                            logger.error("DB error auto-syncing distributor phone: %s", str(db_exc))
                        finally:
                            new_db.close()
            except Exception as e:
                logger.error("Failed to auto-sync distributor phone: %s", str(e), exc_info=True)
                
        elif state in ("close", "closed") and instance_name:
            status_reason = data.get("statusReason") or data.get("reason") or "unknown"
            reason_map = {"401": "logged_out", "408": "timeout", "428": "conflict"}
            disconnect_reason = reason_map.get(str(status_reason), "unknown")
            
            try:
                new_db = SessionLocal()
                try:
                    tenant = new_db.query(DistributorTenant).filter(
                        DistributorTenant.whatsapp_phone_id == instance_name
                    ).first()
                    
                    if tenant and tenant.whatsapp_phone_id:
                        tenant.whatsapp_connection_status = "disconnected"
                        tenant.whatsapp_disconnected_at = datetime.utcnow()
                        tenant.whatsapp_disconnect_reason = disconnect_reason
                        new_db.commit()
                        logger.info("Tenant %s marked disconnected (reason: %s)", 
                                   tenant.id, disconnect_reason)
                finally:
                    new_db.close()
            except Exception as e:
                logger.error("Failed to handle disconnect: %s", str(e))
                
        return {"status": "SUCCESS", "message": "Handshake verified"}
        
    if event_type in ["webhook.test", "webhook.verify"]:
        logger.info("Received gateway validation handshake: %s. Returning immediate success.", event_type)
        return {"status": "SUCCESS", "message": "Handshake verified"}

    # Deduplicate Evolution API retries using the message ID in the raw payload.
    msg_id = payload_data.get("data", {}).get("key", {}).get("id") if isinstance(payload_data.get("data"), dict) else None
    if msg_id and _check_and_mark_msg_id(msg_id):
        logger.info("[Ingestion] Duplicate Evolution API message id=%s — dropping.", msg_id)
        return {"status": "ignored", "message": "Duplicate message already processed"}
        
    payload = WebhookPayload(**payload_data)
    logger.info("[Ingestion - %s] Webhook payload received: %s", correlation_id, payload.model_dump())
    
    # Check if we are running in a pytest environment
    is_testing = "pytest" in sys.modules or "PYTEST_CURRENT_TEST" in os.environ
    
    if is_testing:
        logger.info("[Ingestion - %s] Running synchronously for testing environment", correlation_id)
        return process_whatsapp_webhook_payload(payload, db, correlation_id)
    
    # Otherwise, execute asynchronously using BackgroundTasks
    def run_async():
        db_session = SessionLocal()
        try:
            process_whatsapp_webhook_payload(payload, db_session, correlation_id)
        except Exception as e:
            logger.error("[Ingestion - %s] Async background processing failed: %s", correlation_id, str(e), exc_info=True)
        finally:
            db_session.close()

    background_tasks.add_task(run_async)
    
    return {"status": "received"}


class ProvisionRequest(BaseModel):
    instance_name: str


@router.post("/provision")
async def provision_whatsapp_instance(payload: ProvisionRequest):
    from app.services.gateway_service import EvolutionGatewayService
    import httpx
    try:
        # Reuse a single HTTP connection across the whole flow (delete, init, webhook,
        # QR, status) instead of opening a fresh TCP/TLS connection per call — cuts
        # several round-trips of handshake latency against the remote gateway.
        async with httpx.AsyncClient(timeout=30.0) as client:
            service = EvolutionGatewayService(client=client)

            # Step 1: Force Purge (Defensive Delete)
            delete_url = f"{service.base_url}/instance/delete/{payload.instance_name}"
            logger.info("Purging legacy instance if it exists: url=%s", delete_url)
            legacy_instance_deleted = False
            try:
                response = await client.delete(delete_url, headers=service._get_headers())
                if response.status_code == 404:
                    logger.info("No legacy instance found to purge, moving forward.")
                elif response.status_code not in (200, 201):
                    logger.info("Outbound delete request returned code %d. Proceeding anyway.", response.status_code)
                else:
                    logger.info("Successfully purged legacy instance %s.", payload.instance_name)
                    legacy_instance_deleted = True
            except Exception as delete_exc:
                logger.info("No legacy instance found to purge, moving forward. Details: %s", str(delete_exc))

            # Only wait for the gateway's background WebSocket teardown when we actually
            # deleted a live instance — this is the sole scenario the race condition
            # applies to. Skips a needless 4s stall for first-time/new-tenant provisioning.
            if legacy_instance_deleted:
                logger.info("Waiting 4 seconds for delete operation to fully stabilize...")
                await asyncio.sleep(4)

            # Step 2: Initialize Clean Instance (Do not swallow errors)
            init_res = await service.initialize_instance(payload.instance_name)

            # Step 3: Configure Webhook
            webhook_res = await service.configure_webhook(payload.instance_name)

            # Step 4: Generate QR Session Data
            qr_base64 = await service.generate_qr_code(payload.instance_name)
            conn_status = await service.get_connection_status(payload.instance_name)

        return {
            "status": "success",
            "message": "Instance provisioned successfully",
            "instance_name": payload.instance_name,
            "qr_code": qr_base64,
            "webhook_configured": True,
            "connection_status": conn_status,
            "init_response": init_res,
            "webhook_response": webhook_res
        }
    except Exception as e:
        logger.error("Provisioning failed: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Provisioning failed: {str(e)}"
        )
