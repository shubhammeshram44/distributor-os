import uuid
import logging
import asyncio
from fastapi import APIRouter, Depends, HTTPException, Query, status, Cookie, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.gateway_service import EvolutionGatewayService
import httpx

logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/evolution", tags=["Evolution"])

class EvolutionProvisionRequest(BaseModel):
    instance_name: str | None = None

@router.post("/provision", status_code=status.HTTP_200_OK)
async def provision_instance(
    payload: EvolutionProvisionRequest,
    tenant_id: uuid.UUID | None = None,
    access_token: str | None = Cookie(None),
    authorization: str | None = Header(None)
):
    from app.services.tenant_service import resolve_tenant_id
    try:
        resolved_tenant_id = resolve_tenant_id(tenant_id, access_token, authorization)
    except Exception:
        resolved_tenant_id = None
        
    # Generate unique instance name per tenant
    instance_name = payload.instance_name if payload.instance_name else f"dist-{str(resolved_tenant_id)[:8]}"
    service = EvolutionGatewayService()
    try:
        # Step 1: Force Purge
        # Evolution API returns 403 (not 409) when instance name already exists on /create.
        # Must guarantee clean deletion and memory flush before proceeding.
        import httpx
        delete_url = f"{service.base_url}/instance/delete/{instance_name}"
        logger.info("Purging legacy instance: DELETE %s", delete_url)
        async with httpx.AsyncClient(timeout=15.0) as client:
            del_response = await client.delete(delete_url, headers=service._get_headers())
            logger.info("Delete response: status=%d body=%s",
                        del_response.status_code, del_response.text[:200])
            if del_response.status_code == 404:
                logger.info("No legacy instance found - clean slate.")
            elif del_response.status_code in (200, 201):
                logger.info("Legacy instance purged. Waiting 4s for Evolution API to clear memory...")
                await asyncio.sleep(4)
            else:
                logger.warning("Delete returned %d - proceeding anyway.", del_response.status_code)

        # Step 2: Create fresh instance
        init_res = await service.initialize_instance(instance_name)
        logger.info("Instance created. Waiting 3s for Baileys to initialise...")
        await asyncio.sleep(3)

        # Step 3: Configure Webhook (non-fatal)
        webhook_res = None
        webhook_ok = False
        try:
            webhook_res = await service.configure_webhook(instance_name)
            webhook_ok = True
            logger.info("Webhook configured: %s", webhook_res)
        except Exception as wh_exc:
            logger.warning("Webhook config failed (non-fatal): %s", str(wh_exc))
            webhook_res = {"status": "failed", "reason": str(wh_exc)}

        # Step 4: Fetch QR code
        qr_base64 = await service.generate_qr_code(instance_name)
        conn_status = await service.get_connection_status(instance_name)

        return {
            "status": "success",
            "message": "Instance provisioned successfully" if webhook_ok else "Provisioned - webhook config failed, reconfigure separately",
            "instance_name": instance_name,
            "qr_code": qr_base64,
            "webhook_configured": webhook_ok,
            "connection_status": conn_status,
            "init_response": init_res,
            "webhook_response": webhook_res
        }
    except Exception as e:
        logger.error("Evolution provisioning failed: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Provisioning failed: {str(e)}"
        )

@router.get("/status", status_code=status.HTTP_200_OK)
async def get_instance_status(
    instance_name: str = Query(..., alias="instance_name"),
    tenant_id: uuid.UUID | None = None,
    access_token: str | None = Cookie(None),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db)
):
    service = EvolutionGatewayService()
    try:
        # Fetch connection status details
        url = f"{service.base_url}/instance/connectionState/{instance_name}"
        headers = service._get_headers()
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=headers)
            
        if response.status_code != 200:
            response.raise_for_status()
            
        data = response.json()
        instance_data = data.get("instance") or {}
        conn_status = (
            data.get("connectionStatus")
            or instance_data.get("connectionStatus")
            or instance_data.get("state")
            or instance_data.get("status")
            or "close"
        )
        
        # Sync owner number only when connection flips to open
        owner_jid = None
        if conn_status == "open":
            owner_jid = instance_data.get("owner") or data.get("owner")
            if owner_jid:
                from app.services.tenant_service import resolve_tenant_id
                from app.models.tenant import DistributorTenant
                from app.utils.phone import normalize_phone_number
                from app.services.ingestion_service import IngestionService
                
                try:
                    resolved_tenant_id = resolve_tenant_id(tenant_id, access_token, authorization)
                except Exception:
                    resolved_tenant_id = None
                    
                if resolved_tenant_id:
                    tenant = db.get(DistributorTenant, resolved_tenant_id)
                    if tenant:
                        # Normalize number to standard E.164 (+91XXXXXXXXXX)
                        normalized_owner = normalize_phone_number(owner_jid)
                        
                        # Idempotency check: only write to DB if the number changed
                        if tenant.whatsapp_order_phone != normalized_owner:
                            logger.info(
                                "Event Discriminator Sync: connection status flipped to open. "
                                "Updating whatsapp_order_phone for tenant %s to %s",
                                resolved_tenant_id, normalized_owner
                            )
                            tenant.whatsapp_order_phone = normalized_owner
                            db.commit()
                            
                            # Flush ingestion cache to keep runtime discriminator state fresh
                            IngestionService.invalidate_tenant_cache(resolved_tenant_id)
                            
        return {"status": conn_status, "ownerJid": owner_jid}
    except Exception as e:
        logger.error("Failed to fetch connection status: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch connection status: {str(e)}"
        )


@router.delete("/disconnect", status_code=status.HTTP_200_OK)
async def disconnect_instance(
    instance_name: str = Query(..., alias="instance_name"),
    tenant_id: uuid.UUID | None = None,
    access_token: str | None = Cookie(None),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db)
):
    service = EvolutionGatewayService()
    try:
        # Step 1: Call delete instance on Evolution API
        url = f"{service.base_url}/instance/delete/{instance_name}"
        headers = service._get_headers()
        logger.info("Disconnecting and deleting instance: DELETE %s", url)
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.delete(url, headers=headers)
            
        if response.status_code not in (200, 201, 404):
            logger.warning("Evolution API returned status %d when deleting instance.", response.status_code)
            
        # Step 2: Clear tenant configuration in DB
        from app.services.tenant_service import resolve_tenant_id
        from app.models.tenant import DistributorTenant
        from app.services.ingestion_service import IngestionService
        
        try:
            resolved_tenant_id = resolve_tenant_id(tenant_id, access_token, authorization)
        except Exception:
            resolved_tenant_id = None
            
        if resolved_tenant_id:
            tenant = db.get(DistributorTenant, resolved_tenant_id)
            if tenant:
                tenant.whatsapp_phone_id = None
                tenant.whatsapp_order_phone = None
                db.commit()
                # Invalidate cache
                IngestionService.invalidate_tenant_cache(resolved_tenant_id)
                logger.info("Cleared WhatsApp integration config for tenant %s", resolved_tenant_id)
                
        return {"status": "success", "message": "Instance disconnected successfully"}
    except Exception as e:
        logger.error("Failed to disconnect instance: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to disconnect instance: {str(e)}"
        )
