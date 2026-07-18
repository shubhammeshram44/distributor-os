from fastapi.testclient import TestClient
from app.main import app

def test_health_endpoint():
    client = TestClient(app)
    # Test GET
    response_get = client.get("/health")
    assert response_get.status_code == 200
    assert response_get.json() == {"status": "ok"}

    # Test HEAD
    response_head = client.head("/health")
    assert response_head.status_code == 200
