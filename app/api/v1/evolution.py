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
    authorization: str | None = Header(None),
    db: Session = Depends(get_db)
):
    from app.services.tenant_service import resolve_tenant_id
    from app.models.tenant import DistributorTenant
    
    # 1. Strict auth — never proceed without valid tenant
    try:
        resolved_tenant_id = resolve_tenant_id(tenant_id, access_token, authorization)
        if not resolved_tenant_id:
            raise ValueError("No tenant resolved")
    except Exception:
        raise HTTPException(status_code=401, detail="Authentication required.")

    # 2. Always derive instance name from tenant ID — never accept from frontend
    instance_name = f"dist-{str(resolved_tenant_id)[:8]}"
    
    # 3. Check current state before doing anything
    service = EvolutionGatewayService()
    
    try:
        existing_status = await service.get_connection_status(instance_name)
        if existing_status == "open":
            # Already connected — return current state, don't recreate
            qr_base64 = None
            return {
                "status": "already_connected",
                "message": "WhatsApp is already connected.",
                "instance_name": instance_name,
                "qr_code": None,
                "connection_status": existing_status
            }
    except Exception:
        pass  # Instance doesn't exist yet — proceed to create

    # 4. Check DB for existing instance record
    tenant = db.get(DistributorTenant, resolved_tenant_id)
    
    # 5. Delete any stale instance (with retry), reusing one HTTP connection for the
    # whole flow (delete, init, webhook, QR, status) instead of opening a fresh
    # TCP/TLS connection per call — cuts several round-trips of handshake latency.
    import httpx
    async with httpx.AsyncClient(timeout=30.0) as client:
        service = EvolutionGatewayService(client=client)

        legacy_instance_deleted = False
        for attempt in range(2):
            del_response = await client.delete(
                f"{service.base_url}/instance/delete/{instance_name}",
                headers=service._get_headers()
            )
            logger.info("Delete attempt %d: status=%d", attempt+1, del_response.status_code)
            if del_response.status_code in (200, 201):
                legacy_instance_deleted = True
                break
            if del_response.status_code == 404:
                break
            await asyncio.sleep(2)

        # Only wait for the gateway's background teardown when we actually deleted a
        # live instance — this is the sole scenario the race condition applies to.
        # Skips a needless several-second stall for first-time/new-tenant provisioning.
        if legacy_instance_deleted:
            await asyncio.sleep(3)  # Wait for Evolution API to clear memory

        # 6. Create fresh instance
        init_res = await service.initialize_instance(instance_name)

        # 7. Configure webhook
        try:
            await service.configure_webhook(instance_name)
            webhook_ok = True
        except Exception as wh_exc:
            logger.warning("Webhook config failed: %s", str(wh_exc))
            webhook_ok = False

        # 8. Generate QR
        qr_base64 = await service.generate_qr_code(instance_name)
        conn_status = await service.get_connection_status(instance_name)

    # 9. Update DB with correct instance name (clear phone until QR scanned)
    if tenant:
        tenant.whatsapp_phone_id = instance_name
        tenant.whatsapp_connection_status = "connecting"
        tenant.whatsapp_order_phone = None  # cleared until QR scanned with correct phone
        db.commit()

    return {
        "status": "success",
        "instance_name": instance_name,
        "qr_code": qr_base64,
        "webhook_configured": webhook_ok,
        "connection_status": conn_status
    }

@router.get("/status")
async def get_instance_status(
    tenant_id: uuid.UUID | None = None,
    access_token: str | None = Cookie(None),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db)
):
    from app.services.tenant_service import resolve_tenant_id
    from app.models.tenant import DistributorTenant
    try:
        resolved_tenant_id = resolve_tenant_id(tenant_id, access_token, authorization)
    except Exception:
        raise HTTPException(status_code=401, detail="Authentication required.")

    instance_name = f"dist-{str(resolved_tenant_id)[:8]}"
    service = EvolutionGatewayService()
    
    try:
        # Always query Evolution API directly for real-time status
        conn_status = await service.get_connection_status(instance_name)
        
        # Sync DB with real status
        tenant = db.get(DistributorTenant, resolved_tenant_id)
        if tenant:
            if conn_status == "open" and tenant.whatsapp_connection_status != "connected":
                tenant.whatsapp_connection_status = "connected"
                db.commit()
            elif conn_status != "open" and tenant.whatsapp_connection_status == "connected":
                tenant.whatsapp_connection_status = "disconnected"
                db.commit()
        
        return {
            "status": conn_status,
            "instance_name": instance_name,
            "connected": conn_status == "open",
            "owner_phone": tenant.whatsapp_order_phone if tenant else None
        }
    except Exception as e:
        return {
            "status": "unknown",
            "instance_name": instance_name,
            "connected": False,
            "error": str(e)
        }


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
