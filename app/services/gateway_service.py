import os
import logging
import httpx
from typing import Optional

logger = logging.getLogger("uvicorn.error")

class EvolutionGatewayService:
    def __init__(self, client: Optional[httpx.AsyncClient] = None):
        self.base_url = os.getenv("EVOLUTION_API_URL", "https://evolution-api-latest-vma7.onrender.com").rstrip("/")
        self.api_key = os.getenv("EVOLUTION_API_KEY")
        self._client = client

    def _get_headers(self) -> dict:
        headers = {
            "Content-Type": "application/json"
        }
        if self.api_key:
            headers["apikey"] = self.api_key
        return headers

    def _get_client(self) -> httpx.AsyncClient:
        return self._client if self._client is not None else httpx.AsyncClient()

    async def initialize_instance(self, instance_name: str) -> dict:
        url = f"{self.base_url}/instance/create"
        payload = {
            "instanceName": instance_name,
            "qrcode": True,
            "integration": "WHATSAPP-BAILEYS"
        }
        logger.info("Initializing Evolution API instance: url=%s, payload=%s", url, payload)
        
        client = self._get_client()
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
        finally:
            if self._client is None:
                await client.aclose()

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

        # 2. Connect call to get QR code.
        # Evolution API source (instance.router.ts):
        #   .get(this.routerPath('connect'), ...)
        # routerPath('connect') => '/connect/:instanceName'  (param=true by default)
        # Router mounted at /instance => full path: GET /instance/connect/:instanceName
        # Method is GET, instance name is a URL path param — no request body.
        url = f"{self.base_url}/instance/connect/{instance_name}"
        logger.info("Generating QR code: url=%s method=GET", url)
        
        client = self._get_client()
        try:
            response = await client.get(url, headers=self._get_headers())
            if response.status_code != 200:
                logger.error(
                    "Evolution API QR generation failed. status_code=%d, url=%s, response=%s",
                    response.status_code, url, response.text
                )
                if any(x in response.text.lower() for x in ["open", "connected", "already"]):
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
            
            if any(x in response.text.lower() for x in ["open", "connected"]):
                logger.info("No base64 string found but response suggests instance is already open/connected: %s", response.text)
                return "ALREADY_CONNECTED"
            
            raise RuntimeError("QR code base64 not found in response.")
        except httpx.HTTPStatusError as exc:
            resp_text = exc.response.text
            if any(x in resp_text.lower() for x in ["open", "connected", "already"]):
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
        finally:
            if self._client is None:
                await client.aclose()

    async def configure_webhook(self, instance_name: str) -> dict:
        url = f"{self.base_url}/webhook/set/{instance_name}"
        app_url = os.getenv("APP_URL") or os.getenv("RENDER_EXTERNAL_URL") or "https://distributor-os-backend.onrender.com"
        webhook_url = f"{app_url.rstrip('/')}/api/v1/whatsapp/webhook"
        
        payload = {
            "webhook": {
                "enabled": True,
                "url": webhook_url,
                "byEvents": False,
                "base64": False,
                "events": [
                    "MESSAGES_UPSERT",
                    "CONNECTION_UPDATE"
                ]
            }
        }
        logger.info("Configuring webhook for instance %s: url=%s, payload=%s", instance_name, url, payload)
        
        client = self._get_client()
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
        finally:
            if self._client is None:
                await client.aclose()

    async def get_connection_status(self, instance_name: str) -> str:
        # Evolution API source: .get(this.routerPath('connectionState'), ...)
        # => GET /instance/connectionState/:instanceName
        url = f"{self.base_url}/instance/connectionState/{instance_name}"
        logger.info("Fetching connection status for instance %s: url=%s", instance_name, url)
        
        client = self._get_client()
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
            status = data.get("connectionStatus") or instance_data.get("connectionStatus") or instance_data.get("state") or instance_data.get("status") or "close"
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
        finally:
            if self._client is None:
                await client.aclose()
