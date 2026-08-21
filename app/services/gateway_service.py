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
        # DEBUG: log exactly what the live container sees (masked for safety)
        masked_key = f"{self.api_key[:3]}...{self.api_key[-3:]}" if self.api_key and len(self.api_key) > 6 else ("***" if self.api_key else "None")
        logger.info(
            "GatewayService init: base_url=%s api_key_present=%s api_key=%s len=%s",
            self.base_url, bool(self.api_key), masked_key,
            len(self.api_key) if self.api_key else 0
        )

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

    async def generate_qr_code(self, instance_name: str, poll: bool = True) -> str:
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

            if not poll:
                logger.info("Polling is disabled. Returning QR as None.")
                return None

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

    async def get_connection_status(self, instance_name: str) -> str:
        """GET /instance/connectionState/:instanceName"""
        url = f"{self.base_url}/instance/connectionState/{instance_name}"
        client = self._get_client()
        try:
            response = await client.get(url, headers=self._get_headers(), timeout=5.0)
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

    async def get_connection_status_safe(self, instance_name: str) -> str:
        """
        GET /instance/connectionState/:instanceName
        Uses a short 5.0s timeout and handles connection state lookup safely.
        Returns one of: 'open', 'connecting', 'closed', '404' (if missing), or raises exception for unknown/error states.
        """
        try:
            state = await self.get_connection_status(instance_name)
            # Normalize state
            if state == "open":
                return "open"
            elif state in ("connecting", "connecting_chat"):
                return "connecting"
            else:
                return "closed"
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return "404"
            raise
        except Exception:
            raise

    async def safe_provision_instance(self, instance_name: str, tenant_id: Optional[uuid.UUID] = None, db: Optional[Session] = None) -> dict:
        """
        Idempotent and non-destructive provisioning flow.
        """
        import uuid
        from sqlalchemy.orm import Session
        from app.models.tenant import DistributorTenant
        from fastapi import HTTPException
        
        # 1. Step 1: Safe Status Check
        try:
            status = await self.get_connection_status_safe(instance_name)
        except Exception as exc:
            correlation_id = str(uuid.uuid4())
            logger.error(
                "Evolution API unavailable [Correlation ID: %s] for instance %s on status check: %s",
                correlation_id, instance_name, str(exc)
            )
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "EVOLUTION_UNAVAILABLE",
                    "message": "WhatsApp service could not be reached. No connection changes were made.",
                    "retriable": True,
                    "correlation_id": correlation_id
                }
            )

        # 2. Step 2: Handle States
        if status == "open":
            if db and tenant_id:
                tenant = db.get(DistributorTenant, tenant_id)
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

        elif status in ("connecting", "closed"):
            try:
                qr_code = await self.generate_qr_code(instance_name, poll=False)
            except Exception as exc:
                correlation_id = str(uuid.uuid4())
                logger.error(
                    "Evolution API connection failed [Correlation ID: %s] for instance %s during connect: %s",
                    correlation_id, instance_name, str(exc)
                )
                raise HTTPException(
                    status_code=502,
                    detail={
                        "code": "EVOLUTION_CONNECTION_FAILED",
                        "message": "Failed to establish connection with WhatsApp service. Please try again.",
                        "retriable": True,
                        "correlation_id": correlation_id
                    }
                )

            if qr_code == "ALREADY_CONNECTED":
                if db and tenant_id:
                    tenant = db.get(DistributorTenant, tenant_id)
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

            if db and tenant_id:
                tenant = db.get(DistributorTenant, tenant_id)
                if tenant:
                    tenant.whatsapp_phone_id = instance_name
                    tenant.whatsapp_connection_status = "connecting"
                    db.commit()

            return {
                "status": "connecting",
                "instance_name": instance_name,
                "connection_status": "connecting",
                "connected": False,
                "qr_code": qr_code,
                "retry_after_seconds": 3
            }

        elif status == "404":
            logger.info("Instance %s is missing (404). Creating fresh instance.", instance_name)
            
            try:
                await self.initialize_instance(instance_name)
            except Exception as exc:
                correlation_id = str(uuid.uuid4())
                logger.error(
                    "Evolution API failed to initialize instance [Correlation ID: %s] for %s: %s",
                    correlation_id, instance_name, str(exc)
                )
                raise HTTPException(
                    status_code=502,
                    detail={
                        "code": "EVOLUTION_INITIALIZATION_FAILED",
                        "message": "Failed to initialize WhatsApp instance. Please try again.",
                        "retriable": True,
                        "correlation_id": correlation_id
                    }
                )

            try:
                await self.configure_webhook(instance_name)
            except Exception as wh_exc:
                logger.warning("Webhook configuration failed for new instance %s: %s", instance_name, str(wh_exc))

            try:
                qr_code = await self.generate_qr_code(instance_name, poll=False)
            except Exception as exc:
                logger.warning("Failed to fetch initial QR for new instance %s: %s", instance_name, str(exc))
                qr_code = None

            if db and tenant_id:
                tenant = db.get(DistributorTenant, tenant_id)
                if tenant:
                    tenant.whatsapp_phone_id = instance_name
                    tenant.whatsapp_connection_status = "connecting"
                    db.commit()

            return {
                "status": "connecting",
                "instance_name": instance_name,
                "connection_status": "connecting",
                "connected": False,
                "qr_code": qr_code,
                "retry_after_seconds": 3
            }
