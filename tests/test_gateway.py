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
            elif "instance/connect" in url:
                mock_resp.json.return_value = {"qrcode": {"base64": "data:image/png;base64,mockqr"}}
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
         patch("app.services.gateway_service.EvolutionGatewayService.get_connection_status", new_callable=AsyncMock) as mock_status:
         
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
