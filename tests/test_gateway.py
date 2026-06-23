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
         
        # Mock initialize_instance
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"instance": {"instanceName": "test_bot"}}
        mock_post.return_value = mock_response
        
        res = await service.initialize_instance("test_bot")
        assert res["instance"]["instanceName"] == "test_bot"
        
        # Mock generate_qr_code success
        mock_response_qr = MagicMock()
        mock_response_qr.status_code = 200
        mock_response_qr.json.return_value = {"qrcode": {"base64": "data:image/png;base64,mockqr"}}
        mock_get.return_value = mock_response_qr
        
        # We try connect first in mock since it will match the second URL in list or the first if it returns 200
        # For this test, mock_get returns 200 immediately for the first endpoint in endpoints list
        qr = await service.generate_qr_code("test_bot")
        assert qr == "data:image/png;base64,mockqr"
        
        # Mock configure_webhook
        mock_response_webhook = MagicMock()
        mock_response_webhook.status_code = 200
        mock_response_webhook.json.return_value = {"status": "success"}
        mock_post.return_value = mock_response_webhook
        
        webhook_res = await service.configure_webhook("test_bot")
        assert webhook_res["status"] == "success"
        
        # Mock get_connection_status
        mock_response_status = MagicMock()
        mock_response_status.status_code = 200
        mock_response_status.json.return_value = {"instance": {"status": "open"}}
        mock_get.return_value = mock_response_status
        
        status = await service.get_connection_status("test_bot")
        assert status == "open"


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
