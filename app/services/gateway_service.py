import os
import logging
import httpx
from app.config import settings

logger = logging.getLogger("uvicorn.error")

class EvolutionGatewayService:
    def __init__(self):
        self.base_url = os.getenv("EVOLUTION_API_URL", "https://evolution-api-latest-vma7.onrender.com").rstrip("/")
        self.api_key = os.getenv("EVOLUTION_API_KEY")

    def _get_headers(self):
        headers = {
            "Content-Type": "application/json"
        }
        if self.api_key:
            headers["apikey"] = self.api_key
        return headers

    async def initialize_instance(self, instance_name: str) -> dict:
        url = f"{self.base_url}/instance/create"
        payload = {
            "instanceName": instance_name,
            "qrcode": True,
            "integration": "WHATSAPP-BAILEYS"
        }
        logger.info("Initializing Evolution API instance: url=%s, payload=%s", url, payload)
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=payload, headers=self._get_headers())
                if response.status_code not in (200, 201):
                    logger.error(
                        "Evolution API instance creation failed. status_code=%d, url=%s, payload=%s, response=%s",
                        response.status_code, url, payload, response.text
                    )
                    response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as exc:
                logger.error("HTTP error during instance initialization: url=%s, payload=%s, error=%s", url, payload, str(exc))
                raise
            except Exception as exc:
                logger.error("Unexpected error during instance initialization: url=%s, payload=%s, error=%s", url, payload, str(exc))
                raise

  async def generate_qr_code(self, instance_name: str) -> str:
        # Step 1: Ensure it's initialized (prevents 400/404 errors)
        init_url = f"{self.base_url}/instance/initialize/{instance_name}"
        
        async with httpx.AsyncClient() as client:
            # 1. Initialize
            await client.post(init_url, headers=self._get_headers())
            
            # 2. Connect to get the QR code
            conn_url = f"{self.base_url}/instance/connect/{instance_name}"
            logger.info("Connecting to instance: url=%s", conn_url)
            
            response = await client.post(conn_url, headers=self._get_headers())
            
            if response.status_code != 200:
                logger.error("QR generation failed: %s", response.text)
                response.raise_for_status()
                
            data = response.json()
            
            # Extract base64 safely
            # Note: Sometimes it's in data['qrcode']['base64'], sometimes just data['base64']
            base64_str = data.get("base64") or (data.get("qrcode") or {}).get("base64")
            
            if not base64_str:
                # If it's already 'open', it won't return a QR code. Return a status message.
                if data.get("instance", {}).get("connectionStatus") == "open":
                    return "ALREADY_CONNECTED"
                raise RuntimeError("No QR code found in response.")
            
            return base64_str

    async def configure_webhook(self, instance_name: str) -> dict:
        url = f"{self.base_url}/webhook/set/{instance_name}"
        app_url = os.getenv("APP_URL") or os.getenv("NEXT_PUBLIC_API_URL") or "http://127.0.0.1:8000"
        webhook_url = f"{app_url.rstrip('/')}/api/v1/whatsapp/webhook"
        
        payload = {
            "webhook": {
                "enabled": True,
                "url": webhook_url,
                "byEvents": False,
                "events": [
                    "MESSAGES_UPSERT",
                    "CONNECTION_UPDATE"
                ]
            }
        }
        logger.info("Configuring webhook for instance %s: url=%s, payload=%s", instance_name, url, payload)
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=payload, headers=self._get_headers())
                if response.status_code != 200:
                    logger.error(
                        "Evolution API webhook configuration failed. status_code=%d, url=%s, payload=%s, response=%s",
                        response.status_code, url, payload, response.text
                    )
                    response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as exc:
                logger.error("HTTP error during webhook configuration: url=%s, payload=%s, error=%s", url, payload, str(exc))
                raise
            except Exception as exc:
                logger.error("Unexpected error during webhook configuration: url=%s, payload=%s, error=%s", url, payload, str(exc))
                raise

    async def get_connection_status(self, instance_name: str) -> str:
        url = f"{self.base_url}/instance/connectionState/{instance_name}"
        logger.info("Fetching connection status for instance %s: url=%s", instance_name, url)
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                if response.status_code != 200:
                    logger.error(
                        "Evolution API connection state check failed. status_code=%d, url=%s, response=%s",
                        response.status_code, url, response.text
                    )
                    response.raise_for_status()
                data = response.json()
                instance_data = data.get("instance", {})
                status = instance_data.get("state") or instance_data.get("status") or "close"
                return status
            except httpx.HTTPStatusError as exc:
                logger.error("HTTP error during connection status check: url=%s, error=%s", url, str(exc))
                raise
            except Exception as exc:
                logger.error("Unexpected error during connection status check: url=%s, error=%s", url, str(exc))
                raise
