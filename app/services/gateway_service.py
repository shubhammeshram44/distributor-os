import os
import asyncio
import logging
import httpx
from typing import Optional

logger = logging.getLogger("uvicorn.error")


class EvolutionGatewayService:
    def __init__(self, client: Optional[httpx.AsyncClient] = None):
        self.base_url = os.getenv("EVOLUTION_API_URL", "https://evolution-api-latest-vma7.onrender.com").rstrip("/")
        self.api_key = os.getenv("EVOLUTION_API_KEY")
        self._client = client
        # DEBUG: log exactly what the live container sees
        logger.info(
            "GatewayService init: base_url=%s api_key_present=%s api_key=%s len=%s",
            self.base_url, bool(self.api_key), repr(self.api_key),
            len(self.api_key) if self.api_key else 0
        )

    def _get_headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["apikey"] = self.api_key
        return headers

    def _get_client(self) -> httpx.AsyncClient:
        # 60s timeout to handle Render free tier cold starts (can take up to 45s)
        return self._client if self._client is not None else httpx.AsyncClient(timeout=60.0)

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
            base64_str = self._extract_base64(data, response.text)
            if base64_str:
                logger.info("QR received in Phase 1 response.")
                return base64_str

            # ── Phase 2: poll without re-triggering socket ────────────────────
            # Baileys opens a WebSocket to WhatsApp servers and fires the QR in a callback.
            # On Render free tier this takes 5-20s. We poll /connect which, when state=
            # "connecting", just reads instance.qrCode from memory without resetting the socket.
            logger.info("Phase 2 - QR not ready yet, polling every 3s for up to 45s...")
            consecutive_errors = 0
            for attempt in range(1, 16):  # 15 x 3s = 45 seconds
                await asyncio.sleep(3)

                response = await client.get(url, headers=self._get_headers())
                logger.info("Phase 2 attempt %d/15: status=%d body=%s",
                            attempt, response.status_code, response.text[:500])

                # 404 = instance was auto-deleted by Evolution API (Baileys fatal crash)
                if response.status_code == 404:
                    raise RuntimeError(
                        "Instance was deleted by Evolution API during QR polling. "
                        "Baileys crashed trying to reach WhatsApp servers. "
                        "Check Evolution API logs on Render for the root cause."
                    )

                if response.status_code != 200:
                    response.raise_for_status()

                data = response.json()

                # Detect Baileys crash loop: {"error": true, "message": "[object Object]"}
                if data.get("error") is True:
                    consecutive_errors += 1
                    logger.warning("Baileys error response (consecutive=%d): %s", consecutive_errors, data)
                    if consecutive_errors >= 3:
                        raise RuntimeError(
                            "Baileys is in a crash loop (got 3 consecutive error responses). "
                            "Evolution API cannot reach WhatsApp servers from Render. "
                            "Check Evolution API service logs for the underlying error."
                        )
                    continue
                else:
                    consecutive_errors = 0  # reset on good response

                if data.get("state") == "open" or (data.get("instance", {}) or {}).get("state") == "open":
                    logger.info("Instance became open/connected during poll.")
                    return "ALREADY_CONNECTED"

                base64_str = self._extract_base64(data, response.text)
                if base64_str:
                    logger.info("QR base64 received on Phase 2 attempt %d.", attempt)
                    return base64_str

                count = (data.get("qrcode") or {}).get("count", "?") if isinstance(data.get("qrcode"), dict) else "?"
                logger.info("QR not ready yet (attempt %d/15, count=%s)", attempt, count)

            raise RuntimeError(
                "QR code not received after 45 seconds. "
                "Baileys may be slow to handshake with WhatsApp servers on Render free tier."
            )

        except httpx.HTTPStatusError as exc:
            logger.error("HTTP error during QR fetch: status=%d body=%s",
                         exc.response.status_code, exc.response.text)
            raise
        finally:
            if self._client is None:
                await client.aclose()

    def _extract_base64(self, data: dict, raw_text: str = "") -> Optional[str]:
        """
        Extract base64 QR string from any known response shape Evolution API returns.
        Handles 4 shapes defensively — no KeyError possible.
        """
        # Shape 1: { qrcode: { base64: "..." } }
        qr_block = data.get("qrcode")
        if isinstance(qr_block, dict):
            b = qr_block.get("base64")
            if b and isinstance(b, str):
                return b

        # Shape 2: { base64: "..." } (flat)
        b = data.get("base64")
        if b and isinstance(b, str):
            return b

        # Shape 3: { instance: { qrcode: { base64: "..." } } }
        instance_block = data.get("instance")
        if isinstance(instance_block, dict):
            inner_qr = instance_block.get("qrcode")
            if isinstance(inner_qr, dict):
                b = inner_qr.get("base64")
                if b and isinstance(b, str):
                    return b

        # Shape 4: base64 present somewhere in raw JSON but in an unexpected nesting.
        # Regex fallback — only runs if we have raw text and all dict paths missed.
        if raw_text and "base64" in raw_text:
            import re
            match = re.search(r'"base64"\s*:\s*"([^"]+)"', raw_text)
            if match:
                logger.info("QR base64 extracted via regex fallback.")
                return match.group(1)

        return None

    async def get_current_qr(self, instance_name: str) -> Optional[str]:
        """Single GET to /instance/connect to fetch the current QR without re-triggering socket."""
        url = f"{self.base_url}/instance/connect/{instance_name}"
        client = self._get_client()
        try:
            response = await client.get(url, headers=self._get_headers())
            if response.status_code != 200:
                return None
            data = response.json()
            if data.get("state") == "open" or (data.get("instance", {}) or {}).get("state") == "open":
                return "ALREADY_CONNECTED"
            return self._extract_base64(data, response.text)
        except Exception:
            return None
        finally:
            if self._client is None:
                await client.aclose()

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
