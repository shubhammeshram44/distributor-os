import os
import logging
import httpx
from app.config import settings

logger = logging.getLogger("uvicorn.error")

class EvolutionGatewayService:
    def __init__(self):
        self.base_url = os.getenv("EVOLUTION_API_URL", "https://evolution-api-latest-vma7.onrender.com").rstrip("/")
        self.api_key = os.getenv("EVOLUTION_API_KEY")

    def _get_headers(self) -> dict:
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
                logger.error(
                    "HTTP error during instance initialization: url=%s, payload=%s, status_code=%d, error=%s, response=%s",
                    url, payload, exc.response.status_code, str(exc), exc.response.text
                )
                raise
            except Exception as exc:
                logger.error("Unexpected error during instance initialization: url=%s, payload=%s, error=%s", url, payload, str(exc))
                raise

    async def generate_qr_code(self, instance_name: str) -> str:
        # 1. Defensive Logic: Check connection status first
        try:
            status = await self.get_connection_status(instance_name)
            if status == "open":
                logger.info("Instance %s is already open. Returning 'ALREADY_CONNECTED'.", instance_name)
                return "ALREADY_CONNECTED"
        except Exception as status_exc:
            logger.warning(
                "Could not fetch connection status for %s before QR code generation: %s",
                instance_name, str(status_exc)
            )

        # 2. Proceed to the connection call (POST method for /instance/connect/{instanceName})
        url = f"{self.base_url}/instance/connect/{instance_name}"
        logger.info("Generating QR code: url=%s", url)
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, headers=self._get_headers())
                if response.status_code != 200:
                    logger.error(
                        "Evolution API QR generation failed. status_code=%d, url=%s, response=%s",
                        response.status_code, url, response.text
                    )
                    # Handle case where the connect call returns an error indicating it's already open
                    if "open" in response.text.lower() or "connected" in response.text.lower() or "already" in response.text.lower():
                        logger.info("Connect call response indicates instance is already open/connected: %s", response.text)
                        return "ALREADY_CONNECTED"
                    response.raise_for_status()
                
                data = response.json()
                qrcode_data = data.get("qrcode", {})
                if isinstance(qrcode_data, dict):
                    base64_str = qrcode_data.get("base64")
                else:
                    base64_str = data.get("base64")
                
                if base64_str:
                    return base64_str
                
                # Fallback check of response contents
                if "open" in response.text.lower() or "connected" in response.text.lower():
                    logger.info("No base64 string found but response suggests instance is already open/connected: %s", response.text)
                    return "ALREADY_CONNECTED"
                
                raise RuntimeError("QR code base64 not found in response.")
            except httpx.HTTPStatusError as exc:
                resp_text = exc.response.text
                if "open" in resp_text.lower() or "connected" in resp_text.lower() or "already" in resp_text.lower():
                    logger.info("HTTP Status error indicates already open: %s", resp_text)
                    return "ALREADY_CONNECTED"
                logger.error(
                    "HTTP error during QR code generation: url=%s, status_code=%d, error=%s, response=%s",
                    url, exc.response.status_code, str(exc), resp_text
                )
                raise
            except Exception as exc:
                logger.error("Unexpected error during QR code generation: url=%s, error=%s", url, str(exc))
                raise

    async def configure_webhook(self, instance_name: str) -> dict:
        url = f"{self.base_url}/webhook/instance/set"
        app_url = os.getenv("APP_URL") or os.getenv("NEXT_PUBLIC_API_URL") or "http://127.0.0.1:8000"
        webhook_url = f"{app_url.rstrip('/')}/api/v1/whatsapp/webhook"
        
        payload = {
            "instance": instance_name,
            "url": webhook_url,
            "enabled": True,
            "events": [
                "MESSAGES_UPSERT",
                "CONNECTION_UPDATE"
            ]
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
                logger.error(
                    "HTTP error during webhook configuration: url=%s, payload=%s, status_code=%d, error=%s, response=%s",
                    url, payload, exc.response.status_code, str(exc), exc.response.text
                )
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
                logger.error(
                    "HTTP error during connection status check: url=%s, status_code=%d, error=%s, response=%s",
                    url, exc.response.status_code, str(exc), exc.response.text
                )
                raise
            except Exception as exc:
                logger.error("Unexpected error during connection status check: url=%s, error=%s", url, str(exc))
                raise
