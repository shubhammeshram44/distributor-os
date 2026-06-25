import os
import asyncio
import logging
import httpx
from typing import Optional

logger = logging.getLogger("uvicorn.error")


class EvolutionGatewayService:
    def __init__(self, client: Optional[httpx.AsyncClient] = None):
        self.base_url = os.getenv("EVOLUTION_API_URL", "").rstrip("/")
        self.api_key = os.getenv("EVOLUTION_API_KEY")
        self._client = client

    def _get_headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["apikey"] = self.api_key
        return headers

    def _get_client(self) -> httpx.AsyncClient:
        return self._client if self._client is not None else httpx.AsyncClient(timeout=30.0)

    async def initialize_instance(self, instance_name: str) -> dict:
        """POST /instance/create"""
        url = f"{self.base_url}/instance/create"
        payload = {
            "instanceName": instance_name,
            "qrcode": True,
            "integration": "WHATSAPP-BAILEYS"
        }
        logger.info("Creating instance: POST %s payload=%s", url, payload)
        client = self._get_client()
        try:
            response = await client.post(url, json=payload, headers=self._get_headers())
            logger.info("Create response: status=%d body=%s", response.status_code, response.text[:400])
            if response.status_code not in (200, 201):
                response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            logger.error("HTTP error creating instance: status=%d body=%s",
                         exc.response.status_code, exc.response.text)
            raise
        finally:
            if self._client is None:
                await client.aclose()

    async def configure_webhook(self, instance_name: str) -> dict:
        """POST /webhook/set/:instanceName"""
        url = f"{self.base_url}/webhook/set/{instance_name}"
        app_url = (
            os.getenv("APP_URL")
            or os.getenv("RENDER_EXTERNAL_URL")
            or "https://distributor-os-backend.onrender.com"
        ).rstrip("/")
        webhook_url = f"{app_url}/api/v1/whatsapp/webhook"
        payload = {
            "webhook": {
                "enabled": True,
                "url": webhook_url,
                "byEvents": False,
                "base64": False,
                "events": ["MESSAGES_UPSERT", "CONNECTION_UPDATE"]
            }
        }
        logger.info("Configuring webhook: POST %s url=%s", url, webhook_url)
        client = self._get_client()
        try:
            response = await client.post(url, json=payload, headers=self._get_headers())
            logger.info("Webhook response: status=%d body=%s", response.status_code, response.text[:400])
            if response.status_code != 200:
                response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            logger.error("HTTP error configuring webhook: status=%d body=%s",
                         exc.response.status_code, exc.response.text)
            raise
        finally:
            if self._client is None:
                await client.aclose()

    async def generate_qr_code(self, instance_name: str) -> str:
        """
        Two-phase QR fetch:

        PHASE 1 — Trigger connect ONCE.
          GET /instance/connect/:name
          Evolution API calls connectToWhatsapp() which starts the Baileys socket.
          The controller does its own await delay(2000) then returns instance.qrCode.
          If base64 is already in that first response, great — return it immediately.

        PHASE 2 — If base64 not in first response, poll GET /instance/connect/:name.
          The socket is now in 'connecting' state. Each call to /connect when state='connecting'
          returns instance.qrCode WITHOUT re-triggering connectToWhatsapp (see controller line 323).
          We poll until base64 appears. Render cold starts need up to 30s.
        """
        url = f"{self.base_url}/instance/connect/{instance_name}"
        client = self._get_client()

        try:
            # ── Phase 1: trigger the socket, get first response ──────────────
            logger.info("Phase 1 — triggering connect: GET %s", url)
            response = await client.get(url, headers=self._get_headers())
            logger.info("Phase 1 response: status=%d body=%s",
                        response.status_code, response.text[:500])

            if response.status_code != 200:
                response.raise_for_status()

            data = response.json()

            # Already connected?
            if data.get("state") == "open" or (data.get("instance", {}) or {}).get("state") == "open":
                logger.info("Instance already open.")
                return "ALREADY_CONNECTED"

            # QR in first response? (happens on warm containers)
            base64_str = self._extract_base64(data)
            if base64_str:
                logger.info("QR received in Phase 1 response.")
                return base64_str

            # ── Phase 2: poll without re-triggering socket ────────────────────
            # Wait a beat for Baileys to get past the WhatsApp handshake
            logger.info("Phase 2 — QR not ready yet, polling every 3s for up to 45s...")
            for attempt in range(1, 16):  # 15 attempts × 3s = 45 seconds
                await asyncio.sleep(3)

                response = await client.get(url, headers=self._get_headers())
                logger.info("Phase 2 attempt %d/15: status=%d body=%s",
                            attempt, response.status_code, response.text[:500])

                if response.status_code != 200:
                    response.raise_for_status()

                data = response.json()

                if data.get("state") == "open" or (data.get("instance", {}) or {}).get("state") == "open":
                    logger.info("Instance became open/connected during poll.")
                    return "ALREADY_CONNECTED"

                base64_str = self._extract_base64(data)
                if base64_str:
                    logger.info("QR base64 received on Phase 2 attempt %d.", attempt)
                    return base64_str

                logger.info("QR not ready (attempt %d/15). count=%s",
                            attempt,
                            (data.get("qrcode") or {}).get("count", "?")
                            if isinstance(data.get("qrcode"), dict) else "?")

            raise RuntimeError(
                "QR code not received after 45 seconds. "
                "Check Evolution API logs on Render — Baileys may be failing to reach WhatsApp servers."
            )

        except httpx.HTTPStatusError as exc:
            logger.error("HTTP error during QR fetch: status=%d body=%s",
                         exc.response.status_code, exc.response.text)
            raise
        finally:
            if self._client is None:
                await client.aclose()

    def _extract_base64(self, data: dict) -> Optional[str]:
        """Extract base64 QR string from any known response shape Evolution API returns."""
        # Shape 1: { qrcode: { base64: "..." } }
        qr_block = data.get("qrcode")
        if isinstance(qr_block, dict):
            b = qr_block.get("base64")
            if b:
                return b

        # Shape 2: { base64: "..." } (flat)
        b = data.get("base64")
        if b:
            return b

        # Shape 3: { instance: { qrcode: { base64: "..." } } }
        instance_block = data.get("instance")
        if isinstance(instance_block, dict):
            inner_qr = instance_block.get("qrcode")
            if isinstance(inner_qr, dict):
                b = inner_qr.get("base64")
                if b:
                    return b

        return None

    async def get_connection_status(self, instance_name: str) -> str:
        """GET /instance/connectionState/:instanceName"""
        url = f"{self.base_url}/instance/connectionState/{instance_name}"
        client = self._get_client()
        try:
            response = await client.get(url, headers=self._get_headers())
            logger.info("Connection state: status=%d body=%s",
                        response.status_code, response.text[:300])
            if response.status_code != 200:
                response.raise_for_status()
            data = response.json()
            instance_data = data.get("instance") or {}
            return (
                data.get("connectionStatus")
                or instance_data.get("connectionStatus")
                or instance_data.get("state")
                or instance_data.get("status")
                or "close"
            )
        except httpx.HTTPStatusError as exc:
            logger.error("HTTP error checking connection state: status=%d body=%s",
                         exc.response.status_code, exc.response.text)
            raise
        finally:
            if self._client is None:
                await client.aclose()
