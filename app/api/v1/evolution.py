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
    
    # 1. Strict auth — never proceed without valid tenant
    try:
        resolved_tenant_id = resolve_tenant_id(tenant_id, access_token, authorization)
        if not resolved_tenant_id:
            raise ValueError("No tenant resolved")
    except Exception:
        raise HTTPException(status_code=401, detail="Authentication required.")

    # 2. Always derive instance name from tenant ID — never accept from frontend
    instance_name = f"dist-{str(resolved_tenant_id)[:8]}"
    
    from app.services.gateway_service import EvolutionGatewayService
    import httpx
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        service = EvolutionGatewayService(client=client)
        res = await service.safe_provision_instance(
            instance_name=instance_name,
            tenant_id=resolved_tenant_id,
            db=db
        )
        return res


@router.get("/qr")
async def get_qr_code(
    tenant_id: uuid.UUID | None = None,
    access_token: str | None = Cookie(None),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db)
):
    from app.services.tenant_service import resolve_tenant_id
    from app.models.tenant import DistributorTenant
    try:
        resolved_tenant_id = resolve_tenant_id(tenant_id, access_token, authorization)
        if not resolved_tenant_id:
            raise ValueError("No tenant resolved")
    except Exception:
        raise HTTPException(status_code=401, detail="Authentication required.")

    instance_name = f"dist-{str(resolved_tenant_id)[:8]}"
    
    from app.services.gateway_service import EvolutionGatewayService
    import httpx
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        service = EvolutionGatewayService(client=client)
        try:
            # Check connection status first
            status = await service.get_connection_status_safe(instance_name)
            if status == "open":
                # Sync DB status to connected
                tenant = db.get(DistributorTenant, resolved_tenant_id)
                if tenant:
                    tenant.whatsapp_phone_id = instance_name
                    tenant.whatsapp_connection_status = "connected"
                    db.commit()
                return {
                    "status": "already_connected",
                    "instance_name": instance_name,
                    "connection_status": "open",
                    "connected": True,
                    "qr_code": None
                }
            elif status == "404":
                raise HTTPException(
                    status_code=404,
                    detail="Instance not found. Please provision the instance first."
                )
                
            # Fetch QR without polling
            qr_code = await service.generate_qr_code(instance_name, poll=False)
            if qr_code == "ALREADY_CONNECTED":
                tenant = db.get(DistributorTenant, resolved_tenant_id)
                if tenant:
                    tenant.whatsapp_phone_id = instance_name
                    tenant.whatsapp_connection_status = "connected"
                    db.commit()
                return {
                    "status": "already_connected",
                    "instance_name": instance_name,
                    "connection_status": "open",
                    "connected": True,
                    "qr_code": None
                }
                
            return {
                "status": "connecting",
                "instance_name": instance_name,
                "connection_status": "connecting",
                "connected": False,
                "qr_code": qr_code,
                "retry_after_seconds": 3
            }
        except HTTPException:
            raise
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Evolution API returned error: {exc.response.text}"
            )
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail="Evolution gateway is temporarily unavailable."
            )

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
            logger.error("Failed to delete instance on Evolution API: status=%d body=%s", response.status_code, response.text)
            raise HTTPException(
                status_code=502,
                detail=f"Failed to delete instance on Evolution API (status {response.status_code})."
            )
            
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
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to disconnect instance: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to disconnect instance: {str(e)}"
        )
