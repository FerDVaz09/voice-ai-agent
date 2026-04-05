import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock
from api.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Health & landing
# ---------------------------------------------------------------------------
def test_health_check():
    """El endpoint /health debe retornar JSON {"status": "ok"}."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root_returns_html():
    """La landing page / debe retornar HTML con título de la app."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Sofia AI" in response.text


# ---------------------------------------------------------------------------
# Webhook — call.started
# ---------------------------------------------------------------------------
@patch("api.main.save_call", new_callable=AsyncMock)
def test_webhook_call_started(mock_save):
    mock_save.return_value = "test-uuid"
    payload = {
        "message": {
            "type": "call-started",
            "call": {
                "id": "vapi-123",
                "type": "inbound",
                "customer": {"number": "+18091234567"},
            },
        }
    }
    response = client.post("/webhook/vapi", json=payload)
    assert response.status_code == 200
    assert response.json() == {"received": True}
    mock_save.assert_called_once()


# ---------------------------------------------------------------------------
# Webhook — end-of-call-report
# ---------------------------------------------------------------------------
@patch("api.main.update_call", new_callable=AsyncMock)
def test_webhook_end_of_call(mock_update):
    payload = {
        "message": {
            "type": "end-of-call-report",
            "call": {"id": "vapi-123"},
            "durationSeconds": 120,
            "summary": "Patient scheduled appointment",
            "transcript": "Sofia: Hello...",
        }
    }
    response = client.post("/webhook/vapi", json=payload)
    assert response.status_code == 200
    assert response.json() == {"received": True}
    mock_update.assert_called_once()


# ---------------------------------------------------------------------------
# Webhook — firma inválida
# ---------------------------------------------------------------------------
@patch.dict("os.environ", {"VAPI_WEBHOOK_SECRET": "supersecret"})
def test_webhook_invalid_secret():
    """Debe retornar 403 si el secret no coincide."""
    payload = {"message": {"type": "call-started", "call": {"id": "x"}}}
    response = client.post(
        "/webhook/vapi",
        json=payload,
        headers={"x-vapi-secret": "wrong-secret"},
    )
    assert response.status_code == 403


@patch.dict("os.environ", {"VAPI_WEBHOOK_SECRET": "supersecret"})
@patch("api.main.save_call", new_callable=AsyncMock)
def test_webhook_valid_secret(mock_save):
    """Debe pasar con el secret correcto."""
    mock_save.return_value = "uuid"
    payload = {
        "message": {
            "type": "call-started",
            "call": {
                "id": "vapi-456",
                "type": "inbound",
                "customer": {"number": "+573001234567"},
            },
        }
    }
    response = client.post(
        "/webhook/vapi",
        json=payload,
        headers={"x-vapi-secret": "supersecret"},
    )
    assert response.status_code == 200
