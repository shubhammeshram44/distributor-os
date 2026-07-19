import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from app.main import app
from app.services.gateway_service import EvolutionGatewayService

client = TestClient(app)

@pytest.mark.anyio
async def test_evolution_gateway_service_methods():
    service = EvolutionGatewayService()
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post, \
         patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
         
        # Define post side effects
        def post_side_effect(url, **kwargs):
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            if "instance/create" in url:
                mock_resp.status_code = 201
                mock_resp.json.return_value = {"instance": {"instanceName": "test_bot"}}
            elif "webhook/set" in url:
                mock_resp.json.return_value = {"status": "success"}
            return mock_resp
        mock_post.side_effect = post_side_effect

        # Define get side effects where status is closed
        def get_close_side_effect(url, **kwargs):
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            if "connectionState" in url:
                mock_resp.json.return_value = {"instance": {"status": "close"}}
            elif "instance/connect" in url:
                mock_resp.json.return_value = {"qrcode": {"base64": "data:image/png;base64,mockqr"}}
            return mock_resp
        mock_get.side_effect = get_close_side_effect

        # 1. Test initialize_instance
        res = await service.initialize_instance("test_bot")
        assert res["instance"]["instanceName"] == "test_bot"
        
        # 2. Test generate_qr_code when closed (should call connect POST and return mockqr base64)
        qr = await service.generate_qr_code("test_bot")
        assert qr == "data:image/png;base64,mockqr"
        
        # 3. Test configure_webhook
        webhook_res = await service.configure_webhook("test_bot")
        assert webhook_res["status"] == "success"
        
        # 4. Test get_connection_status
        # Change mock_get side effect to return open status
        def get_open_side_effect(url, **kwargs):
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            if "connectionState" in url:
                mock_resp.json.return_value = {"instance": {"status": "open"}}
            elif "instance/connect" in url:
                mock_resp.json.return_value = {"instance": {"state": "open"}}
            return mock_resp
        mock_get.side_effect = get_open_side_effect
        
        status = await service.get_connection_status("test_bot")
        assert status == "open"

        # 5. Test generate_qr_code when open (should immediately return ALREADY_CONNECTED)
        qr_open = await service.generate_qr_code("test_bot")
        assert qr_open == "ALREADY_CONNECTED"


def test_provision_endpoint_success():
    with patch("app.services.gateway_service.EvolutionGatewayService.initialize_instance", new_callable=AsyncMock) as mock_init, \
         patch("app.services.gateway_service.EvolutionGatewayService.configure_webhook", new_callable=AsyncMock) as mock_webhook, \
         patch("app.services.gateway_service.EvolutionGatewayService.generate_qr_code", new_callable=AsyncMock) as mock_qr, \
         patch("app.services.gateway_service.EvolutionGatewayService.get_connection_status", new_callable=AsyncMock) as mock_status, \
         patch("httpx.AsyncClient.delete", new_callable=AsyncMock) as mock_delete:
         
        mock_delete.return_value = MagicMock(status_code=404)
        mock_init.return_value = {"status": "created"}
        mock_webhook.return_value = {"status": "webhook_set"}
        mock_qr.return_value = "data:image/png;base64,mockqr"
        mock_status.return_value = "open"
        
        response = client.post(
            "/api/v1/whatsapp/provision",
            json={"instance_name": "test_bot"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["qr_code"] == "data:image/png;base64,mockqr"
        assert data["connection_status"] == "open"


def test_evolution_provision_endpoint_optional_instance_name(monkeypatch):
    with patch("app.services.gateway_service.EvolutionGatewayService.initialize_instance", new_callable=AsyncMock) as mock_init, \
         patch("app.services.gateway_service.EvolutionGatewayService.configure_webhook", new_callable=AsyncMock) as mock_webhook, \
         patch("app.services.gateway_service.EvolutionGatewayService.generate_qr_code", new_callable=AsyncMock) as mock_qr, \
         patch("app.services.gateway_service.EvolutionGatewayService.get_connection_status", new_callable=AsyncMock) as mock_status, \
         patch("httpx.AsyncClient.delete", new_callable=AsyncMock) as mock_delete:
         
        mock_delete.return_value = MagicMock(status_code=404)
        mock_init.return_value = {"status": "created"}
        mock_webhook.return_value = {"status": "webhook_set"}
        mock_qr.return_value = "data:image/png;base64,mockqr"
        mock_status.return_value = "close"
        
        # Mock resolve_tenant_id to return a fixed UUID
        fake_uuid = "7e8bed10-8339-446f-b851-de96ab5f0cad"
        from app.services import tenant_service
        monkeypatch.setattr(tenant_service, "resolve_tenant_id", lambda *args, **kwargs: fake_uuid)

        # Call without sending instance_name
        response = client.post(
            "/api/v1/evolution/provision",
            json={}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["instance_name"] == "dist-7e8bed10"
        assert data["qr_code"] == "data:image/png;base64,mockqr"


def test_evolution_provision_endpoint_already_connected(monkeypatch):
    with patch("app.services.gateway_service.EvolutionGatewayService.get_connection_status", new_callable=AsyncMock) as mock_status:
        mock_status.return_value = "open"
        
        fake_uuid = "7e8bed10-8339-446f-b851-de96ab5f0cad"
        from app.services import tenant_service
        monkeypatch.setattr(tenant_service, "resolve_tenant_id", lambda *args, **kwargs: fake_uuid)

        response = client.post(
            "/api/v1/evolution/provision",
            json={}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "already_connected"
        assert data["instance_name"] == "dist-7e8bed10"
        assert data["qr_code"] is None
        assert data["connection_status"] == "open"


def test_evolution_disconnect_endpoint_success(monkeypatch, db_session):
    import uuid
    from app.models.tenant import DistributorTenant
    
    tenant = DistributorTenant(
        id=uuid.UUID("7e8bed10-8339-446f-b851-de96ab5f0cad"),
        name="Disconnect Test Tenant",
        whatsapp_phone_id="test-instance",
        whatsapp_order_phone="+919078158448"
    )
    db_session.add(tenant)
    db_session.commit()
    
    with patch("httpx.AsyncClient.delete", new_callable=AsyncMock) as mock_delete:
        mock_delete.return_value = MagicMock(status_code=200)
        mock_delete.return_value.json = lambda: {"status": "deleted"}
        
        # Mock resolve_tenant_id to return our tenant ID
        from app.services import tenant_service
        monkeypatch.setattr(tenant_service, "resolve_tenant_id", lambda *args, **kwargs: tenant.id)
        
        # Override get_db in endpoint to use our db_session
        from app.main import app
        from app.database import get_db
        app.dependency_overrides[get_db] = lambda: db_session

        response = client.delete(
            "/api/v1/evolution/disconnect?instance_name=test-instance"
        )
        
        # Clean overrides
        app.dependency_overrides.clear()
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["message"] == "Instance disconnected successfully"
        
        # Verify db fields cleared
        db_session.expire_all()
        updated_tenant = db_session.query(DistributorTenant).filter_by(id=tenant.id).one()
        assert updated_tenant.whatsapp_phone_id is None
        assert updated_tenant.whatsapp_order_phone is None


def test_evolution_provision_skips_stabilization_sleep_when_nothing_deleted(monkeypatch):
    """
    Regression test: /evolution/provision previously slept unconditionally (~6-8s
    total across a delete-retry loop + two fixed "wait for Evolution API" sleeps) on
    every call, even for a brand-new tenant with no existing instance to tear down.
    This directly caused the WhatsApp-connection lag reported by users. The sleep
    that waits for the gateway to "clear memory" after a delete should only run when
    a legacy instance actually existed and was deleted (delete_response 200/201) —
    not when there was nothing to delete (404).
    """
    with patch("app.services.gateway_service.EvolutionGatewayService.initialize_instance", new_callable=AsyncMock) as mock_init, \
         patch("app.services.gateway_service.EvolutionGatewayService.configure_webhook", new_callable=AsyncMock) as mock_webhook, \
         patch("app.services.gateway_service.EvolutionGatewayService.generate_qr_code", new_callable=AsyncMock) as mock_qr, \
         patch("app.services.gateway_service.EvolutionGatewayService.get_connection_status", new_callable=AsyncMock) as mock_status, \
         patch("httpx.AsyncClient.delete", new_callable=AsyncMock) as mock_delete, \
         patch("app.api.v1.evolution.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:

        mock_delete.return_value = MagicMock(status_code=404)
        mock_init.return_value = {"status": "created"}
        mock_webhook.return_value = {"status": "webhook_set"}
        mock_qr.return_value = "data:image/png;base64,mockqr"
        # First call (pre-check) returns "close" so the fast-path "already_connected"
        # return isn't taken; second call (final status) also "close".
        mock_status.return_value = "close"

        fake_uuid = "7e8bed10-8339-446f-b851-de96ab5f0cad"
        from app.services import tenant_service
        monkeypatch.setattr(tenant_service, "resolve_tenant_id", lambda *args, **kwargs: fake_uuid)

        response = client.post("/api/v1/evolution/provision", json={})

        assert response.status_code == 200
        assert response.json()["status"] == "success"
        # Nothing existed to delete (404) — the "wait for Evolution API to clear
        # memory" sleep must be skipped entirely.
        mock_sleep.assert_not_called()


def test_evolution_provision_still_waits_after_deleting_legacy_instance(monkeypatch):
    """
    When a legacy instance genuinely existed and was deleted (200/201), the brief
    stabilization sleep must still run — this preserves the original race-condition
    protection for the one scenario it was meant to guard against.
    """
    with patch("app.services.gateway_service.EvolutionGatewayService.initialize_instance", new_callable=AsyncMock) as mock_init, \
         patch("app.services.gateway_service.EvolutionGatewayService.configure_webhook", new_callable=AsyncMock) as mock_webhook, \
         patch("app.services.gateway_service.EvolutionGatewayService.generate_qr_code", new_callable=AsyncMock) as mock_qr, \
         patch("app.services.gateway_service.EvolutionGatewayService.get_connection_status", new_callable=AsyncMock) as mock_status, \
         patch("httpx.AsyncClient.delete", new_callable=AsyncMock) as mock_delete, \
         patch("app.api.v1.evolution.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:

        mock_delete.return_value = MagicMock(status_code=200)
        mock_init.return_value = {"status": "created"}
        mock_webhook.return_value = {"status": "webhook_set"}
        mock_qr.return_value = "data:image/png;base64,mockqr"
        mock_status.return_value = "close"

        fake_uuid = "7e8bed10-8339-446f-b851-de96ab5f0cad"
        from app.services import tenant_service
        monkeypatch.setattr(tenant_service, "resolve_tenant_id", lambda *args, **kwargs: fake_uuid)

        response = client.post("/api/v1/evolution/provision", json={})

        assert response.status_code == 200
        # A legacy instance was actually deleted — the stabilization sleep must run.
        mock_sleep.assert_called_once()


