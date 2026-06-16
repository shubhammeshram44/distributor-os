import pytest
from unittest.mock import patch, MagicMock
import requests
from app.config import settings
from app.services.sms_factory import get_sms_gateway
from app.services.sms_providers import MSG91Provider, TwilioSMSProvider

def test_sms_factory_resolution():
    # Test resolution for MSG91
    with patch.object(settings, "SMS_PROVIDER", "MSG91"):
        with patch.object(settings, "SMS_GATEWAY_API_KEY", "test_msg91_key"):
            gateway = get_sms_gateway()
            assert isinstance(gateway, MSG91Provider)
            assert gateway.auth_key == "test_msg91_key"

    # Test resolution for TWILIO
    with patch.object(settings, "SMS_PROVIDER", "TWILIO"):
        with patch.object(settings, "SMS_GATEWAY_API_KEY", "test_twilio_key"):
            gateway = get_sms_gateway()
            assert isinstance(gateway, TwilioSMSProvider)
            assert gateway.api_key == "test_twilio_key"

    # Test resolution error for unsupported provider
    with patch.object(settings, "SMS_PROVIDER", "EXOTEL"):
        with pytest.raises(ValueError) as excinfo:
            get_sms_gateway()
        assert "Unsupported SMS_PROVIDER" in str(excinfo.value)

@patch("requests.post")
def test_msg91_send_otp_success(mock_post):
    # Set up mock response
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "Success"
    mock_post.return_value = mock_resp

    provider = MSG91Provider(auth_key="test_auth_key")
    result = provider.send_otp(mobile_number="+919999999999", otp_code="123456")

    assert result["success"] is True
    assert "OTP dispatched" in result["message"]

    # Verify requests.post was called with correctly stripped mobile number
    mock_post.assert_called_once_with(
        "https://control.msg91.com/api/v5/otp",
        json={"otp": "123456", "mobile": "919999999999"},
        headers={"authkey": "test_auth_key", "Content-Type": "application/json"},
        timeout=10
    )

@patch("requests.post")
def test_msg91_send_otp_failure_status(mock_post):
    # Mock failure response status code (e.g. 400)
    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.text = "Invalid Auth Key"
    mock_post.return_value = mock_resp

    provider = MSG91Provider(auth_key="invalid_key")
    result = provider.send_otp(mobile_number="+919999999999", otp_code="123456")

    assert result["success"] is False
    assert "MSG91 dispatch failed" in result["message"]

@patch("requests.post")
def test_msg91_send_otp_timeout(mock_post):
    # Mock requests timeout
    mock_post.side_effect = requests.exceptions.Timeout("Timeout error")

    provider = MSG91Provider(auth_key="test_auth_key")
    result = provider.send_otp(mobile_number="+919999999999", otp_code="123456")

    assert result["success"] is False
    assert "timed out" in result["message"]

@patch("requests.get")
def test_msg91_verify_otp_success(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"type": "success", "message": "OTP verified successfully"}
    mock_get.return_value = mock_resp

    provider = MSG91Provider(auth_key="test_auth_key")
    result = provider.verify_otp_gateway(mobile_number="+919999999999", otp_code="123456")

    assert result["verified"] is True
    assert "OTP verified" in result["message"]

    mock_get.assert_called_once_with(
        "https://control.msg91.com/api/v5/otp/verify",
        headers={"authkey": "test_auth_key"},
        params={"mobile": "919999999999", "otp": "123456"},
        timeout=10
    )

@patch("requests.get")
def test_msg91_verify_otp_invalid(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"type": "error", "message": "already_verified"}
    mock_get.return_value = mock_resp

    provider = MSG91Provider(auth_key="test_auth_key")
    result = provider.verify_otp_gateway(mobile_number="+919999999999", otp_code="123456")

    assert result["verified"] is False
    assert "already_verified" in result["message"]
