import uuid
import logging
import asyncio
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from app.database import get_db
from app.services.gateway_service import EvolutionGatewayService

logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/evolution", tags=["Evolution"])

class EvolutionProvisionRequest(BaseModel):
    instance_name: str

@router.post("/provision", status_code=status.HTTP_200_OK)
async def provision_instance(payload: EvolutionProvisionRequest):
    service = EvolutionGatewayService()
    try:
        # Step 1: Force Purge
        # Evolution API returns 403 (not 409) when instance name already exists on /create.
        # Must guarantee clean deletion and memory flush before proceeding.
        import httpx
        delete_url = f"{service.base_url}/instance/delete/{payload.instance_name}"
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
        init_res = await service.initialize_instance(payload.instance_name)
        logger.info("Instance created. Waiting 3s for Baileys to initialise...")
        await asyncio.sleep(3)

        # Step 3: Configure Webhook (non-fatal)
        webhook_res = None
        webhook_ok = False
        try:
            webhook_res = await service.configure_webhook(payload.instance_name)
            webhook_ok = True
            logger.info("Webhook configured: %s", webhook_res)
        except Exception as wh_exc:
            logger.warning("Webhook config failed (non-fatal): %s", str(wh_exc))
            webhook_res = {"status": "failed", "reason": str(wh_exc)}

        # Step 4: Fetch QR code
        qr_base64 = await service.generate_qr_code(payload.instance_name)
        conn_status = await service.get_connection_status(payload.instance_name)

        return {
            "status": "success",
            "message": "Instance provisioned successfully" if webhook_ok else "Provisioned - webhook config failed, reconfigure separately",
            "instance_name": payload.instance_name,
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
async def get_instance_status(instance_name: str = Query(..., alias="instance_name")):
    service = EvolutionGatewayService()
    try:
        conn_status = await service.get_connection_status(instance_name)
        return {"status": conn_status}
    except Exception as e:
        logger.error("Failed to fetch connection status: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch connection status: {str(e)}"
        )

@router.get("/qr", status_code=status.HTTP_200_OK)
async def get_instance_qr(instance_name: str = Query(..., alias="instance_name")):
    """Fetch the current QR code without reprovisioning. Used for periodic QR refresh."""
    service = EvolutionGatewayService()
    try:
        result = await service.get_current_qr(instance_name)
        if result == "ALREADY_CONNECTED":
            return {"status": "open", "qr_code": None}
        return {"status": "connecting", "qr_code": result}
    except Exception as e:
        logger.error("Failed to fetch QR: %s", str(e))
        raise HTTPException(status_code=500, detail=f"Failed to fetch QR: {str(e)}")
