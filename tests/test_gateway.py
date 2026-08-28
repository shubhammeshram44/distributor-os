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


def test_provision_endpoint_success(monkeypatch):
    """
    Test that /api/v1/whatsapp/provision (adapted) returns success when status is open
    """
    with patch("app.services.gateway_service.EvolutionGatewayService.get_connection_status_safe", new_callable=AsyncMock) as mock_status:
        mock_status.return_value = "open"
        
        fake_uuid = "7e8bed10-8339-446f-b851-de96ab5f0cad"
        from app.services import tenant_service
        monkeypatch.setattr(tenant_service, "resolve_tenant_id", lambda *args, **kwargs: fake_uuid)
        
        response = client.post(
            "/api/v1/whatsapp/provision",
            json={"instance_name": "test_bot"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["connection_status"] == "open"


def test_evolution_provision_endpoint_optional_instance_name(monkeypatch):
    """
    Test /api/v1/evolution/provision returns connecting when status is closed
    """
    with patch("app.services.gateway_service.EvolutionGatewayService.get_connection_status_safe", new_callable=AsyncMock) as mock_status, \
         patch("app.services.gateway_service.EvolutionGatewayService.generate_qr_code", new_callable=AsyncMock) as mock_qr:
         
        mock_status.return_value = "closed"
        mock_qr.return_value = "data:image/png;base64,mockqr"
        
        fake_uuid = "7e8bed10-8339-446f-b851-de96ab5f0cad"
        from app.services import tenant_service
        monkeypatch.setattr(tenant_service, "resolve_tenant_id", lambda *args, **kwargs: fake_uuid)

        response = client.post(
            "/api/v1/evolution/provision",
            json={}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "connecting"
        assert data["instance_name"] == "dist-7e8bed10"
        assert data["qr_code"] == "data:image/png;base64,mockqr"


def test_evolution_provision_endpoint_already_connected(monkeypatch):
    with patch("app.services.gateway_service.EvolutionGatewayService.get_connection_status_safe", new_callable=AsyncMock) as mock_status:
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
        whatsapp_order_phone="+919078158448",
        whatsapp_connection_status="connected",
    )
    db_session.add(tenant)
    db_session.commit()
    
    with patch("httpx.AsyncClient.delete", new_callable=AsyncMock) as mock_delete:
        mock_delete.return_value = MagicMock(status_code=200)
        mock_delete.return_value.json = lambda: {"status": "deleted"}
        
        from app.services import tenant_service
        monkeypatch.setattr(tenant_service, "resolve_tenant_id", lambda *args, **kwargs: tenant.id)
        
        from app.main import app
        from app.database import get_db
        app.dependency_overrides[get_db] = lambda: db_session

        response = client.delete(
            "/api/v1/evolution/disconnect?instance_name=test-instance"
        )
        app.dependency_overrides.clear()
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        
        db_session.expire_all()
        updated_tenant = db_session.query(DistributorTenant).filter_by(id=tenant.id).one()
        assert updated_tenant.whatsapp_phone_id is None
        assert updated_tenant.whatsapp_order_phone is None
        # Regression test for WA-5: disconnect must also update the
        # connection-status fields, not just the phone/instance config --
        # otherwise GET .../whatsapp-status keeps reporting "connected"
        # even though the instance was just deleted on Evolution API.
        assert updated_tenant.whatsapp_connection_status == "disconnected"
        assert updated_tenant.whatsapp_disconnected_at is not None
        assert updated_tenant.whatsapp_disconnect_reason == "manual_disconnect"


def test_evolution_disconnect_endpoint_failure_stops_db_clear(monkeypatch, db_session):
    import uuid
    from app.models.tenant import DistributorTenant
    
    tenant = DistributorTenant(
        id=uuid.UUID("7e8bed10-8339-446f-b851-de96ab5f0cad"),
        name="Disconnect Failure Test Tenant",
        whatsapp_phone_id="test-instance",
        whatsapp_order_phone="+919078158448"
    )
    db_session.add(tenant)
    db_session.commit()
    
    with patch("httpx.AsyncClient.delete", new_callable=AsyncMock) as mock_delete:
        # Evolution API fails with a 400 Bad Request
        mock_delete.return_value = MagicMock(status_code=400, text="Bad Request")
        
        from app.services import tenant_service
        monkeypatch.setattr(tenant_service, "resolve_tenant_id", lambda *args, **kwargs: tenant.id)
        
        from app.main import app
        from app.database import get_db
        app.dependency_overrides[get_db] = lambda: db_session

        response = client.delete(
            "/api/v1/evolution/disconnect?instance_name=test-instance"
        )
        app.dependency_overrides.clear()
        
        # Should raise 502 Bad Gateway
        assert response.status_code == 502
        
        # Verify db fields are NOT cleared
        db_session.expire_all()
        updated_tenant = db_session.query(DistributorTenant).filter_by(id=tenant.id).one()
        assert updated_tenant.whatsapp_phone_id == "test-instance"
        assert updated_tenant.whatsapp_order_phone == "+919078158448"


def test_state_machine_open_does_no_delete_or_create(monkeypatch):
    with patch("app.services.gateway_service.EvolutionGatewayService.get_connection_status_safe", new_callable=AsyncMock) as mock_status, \
         patch("app.services.gateway_service.EvolutionGatewayService.initialize_instance", new_callable=AsyncMock) as mock_init, \
         patch("httpx.AsyncClient.delete", new_callable=AsyncMock) as mock_delete:
         
        mock_status.return_value = "open"
        
        fake_uuid = "7e8bed10-8339-446f-b851-de96ab5f0cad"
        from app.services import tenant_service
        monkeypatch.setattr(tenant_service, "resolve_tenant_id", lambda *args, **kwargs: fake_uuid)

        response = client.post("/api/v1/evolution/provision", json={})
        assert response.status_code == 200
        assert response.json()["status"] == "already_connected"
        
        mock_init.assert_not_called()
        mock_delete.assert_not_called()


def test_state_machine_connecting_does_no_delete_or_create(monkeypatch):
    with patch("app.services.gateway_service.EvolutionGatewayService.get_connection_status_safe", new_callable=AsyncMock) as mock_status, \
         patch("app.services.gateway_service.EvolutionGatewayService.generate_qr_code", new_callable=AsyncMock) as mock_qr, \
         patch("app.services.gateway_service.EvolutionGatewayService.initialize_instance", new_callable=AsyncMock) as mock_init, \
         patch("httpx.AsyncClient.delete", new_callable=AsyncMock) as mock_delete:
         
        mock_status.return_value = "connecting"
        mock_qr.return_value = "data:image/png;base64,mockqr"
        
        fake_uuid = "7e8bed10-8339-446f-b851-de96ab5f0cad"
        from app.services import tenant_service
        monkeypatch.setattr(tenant_service, "resolve_tenant_id", lambda *args, **kwargs: fake_uuid)

        response = client.post("/api/v1/evolution/provision", json={})
        assert response.status_code == 200
        assert response.json()["status"] == "connecting"
        
        mock_init.assert_not_called()
        mock_delete.assert_not_called()


def test_state_machine_missing_404_creates_instance(monkeypatch):
    with patch("app.services.gateway_service.EvolutionGatewayService.get_connection_status_safe", new_callable=AsyncMock) as mock_status, \
         patch("app.services.gateway_service.EvolutionGatewayService.initialize_instance", new_callable=AsyncMock) as mock_init, \
         patch("app.services.gateway_service.EvolutionGatewayService.configure_webhook", new_callable=AsyncMock) as mock_webhook, \
         patch("app.services.gateway_service.EvolutionGatewayService.generate_qr_code", new_callable=AsyncMock) as mock_qr:
         
        mock_status.return_value = "404"
        mock_init.return_value = {"status": "created"}
        mock_webhook.return_value = {"status": "success"}
        mock_qr.return_value = "data:image/png;base64,mockqr"
        
        fake_uuid = "7e8bed10-8339-446f-b851-de96ab5f0cad"
        from app.services import tenant_service
        monkeypatch.setattr(tenant_service, "resolve_tenant_id", lambda *args, **kwargs: fake_uuid)

        response = client.post("/api/v1/evolution/provision", json={})
        assert response.status_code == 200
        assert response.json()["status"] == "connecting"
        
        mock_init.assert_called_once()
        mock_webhook.assert_called_once()


def test_state_machine_unknown_status_raises_503(monkeypatch):
    with patch("app.services.gateway_service.EvolutionGatewayService.get_connection_status_safe", new_callable=AsyncMock) as mock_status, \
         patch("app.services.gateway_service.EvolutionGatewayService.initialize_instance", new_callable=AsyncMock) as mock_init:
         
        mock_status.side_effect = Exception("Gateway Timeout")
        
        fake_uuid = "7e8bed10-8339-446f-b851-de96ab5f0cad"
        from app.services import tenant_service
        monkeypatch.setattr(tenant_service, "resolve_tenant_id", lambda *args, **kwargs: fake_uuid)

        response = client.post("/api/v1/evolution/provision", json={})
        assert response.status_code == 503
        data = response.json()
        assert data["detail"]["code"] == "EVOLUTION_UNAVAILABLE"
        
        mock_init.assert_not_called()


def test_qr_endpoint_open(monkeypatch, db_session):
    import uuid
    from app.models.tenant import DistributorTenant
    
    tenant = DistributorTenant(
        id=uuid.UUID("7e8bed10-8339-446f-b851-de96ab5f0cad"),
        name="QR Tenant",
        whatsapp_phone_id=None,
        whatsapp_connection_status="disconnected"
    )
    db_session.add(tenant)
    db_session.commit()
    
    with patch("app.services.gateway_service.EvolutionGatewayService.get_connection_status_safe", new_callable=AsyncMock) as mock_status:
        mock_status.return_value = "open"
        
        from app.services import tenant_service
        monkeypatch.setattr(tenant_service, "resolve_tenant_id", lambda *args, **kwargs: tenant.id)
        
        from app.main import app
        from app.database import get_db
        app.dependency_overrides[get_db] = lambda: db_session

        response = client.get("/api/v1/evolution/qr")
        app.dependency_overrides.clear()
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "already_connected"
        assert data["connection_status"] == "open"
        assert data["qr_code"] is None
        
        db_session.expire_all()
        updated_tenant = db_session.query(DistributorTenant).filter_by(id=tenant.id).one()
        assert updated_tenant.whatsapp_connection_status == "connected"


def test_qr_endpoint_connecting(monkeypatch):
    with patch("app.services.gateway_service.EvolutionGatewayService.get_connection_status_safe", new_callable=AsyncMock) as mock_status, \
         patch("app.services.gateway_service.EvolutionGatewayService.generate_qr_code", new_callable=AsyncMock) as mock_qr:
         
        mock_status.return_value = "connecting"
        mock_qr.return_value = "data:image/png;base64,mockqr"
        
        fake_uuid = "7e8bed10-8339-446f-b851-de96ab5f0cad"
        from app.services import tenant_service
        monkeypatch.setattr(tenant_service, "resolve_tenant_id", lambda *args, **kwargs: fake_uuid)

        response = client.get("/api/v1/evolution/qr")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "connecting"
        assert data["qr_code"] == "data:image/png;base64,mockqr"


def test_qr_endpoint_missing_404(monkeypatch):
    with patch("app.services.gateway_service.EvolutionGatewayService.get_connection_status_safe", new_callable=AsyncMock) as mock_status:
        mock_status.return_value = "404"
        
        fake_uuid = "7e8bed10-8339-446f-b851-de96ab5f0cad"
        from app.services import tenant_service
        monkeypatch.setattr(tenant_service, "resolve_tenant_id", lambda *args, **kwargs: fake_uuid)

        response = client.get("/api/v1/evolution/qr")
        assert response.status_code == 404


