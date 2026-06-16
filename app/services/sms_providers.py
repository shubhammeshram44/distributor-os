"""
SMS Provider Implementations
==============================
Concrete subclasses for each supported SMS vendor.
All network I/O is wrapped in try-except blocks with timeouts
to insulate database transactions from external failures.
"""

import httpx
import requests
from app.services.sms_base import BaseSMSProvider
from app.config import settings



class TwilioSMSProvider(BaseSMSProvider):
    """
    Twilio SMS gateway implementation.
    Uses Twilio's REST API to send transactional SMS messages.
    Requires SMS_GATEWAY_API_KEY to be set to a Twilio Auth Token,
    and the Account SID to be embedded in the key as 'SID:TOKEN' or
    configured separately. For simplicity, we use a single key format.
    """

    TWILIO_API_BASE = "https://api.twilio.com/2010-04-01"

    def __init__(self):
        self.api_key = settings.SMS_GATEWAY_API_KEY
        # Support composite key format: "ACCOUNT_SID:AUTH_TOKEN"
        if ":" in self.api_key:
            self.account_sid, self.auth_token = self.api_key.split(":", 1)
        else:
            self.account_sid = self.api_key
            self.auth_token = self.api_key

    def send_otp(self, mobile_number: str, otp_code: str) -> dict:
        """Send OTP via Twilio Programmable SMS."""
        url = f"{self.TWILIO_API_BASE}/Accounts/{self.account_sid}/Messages.json"
        body = f"Your DistributorOS verification code is: {otp_code}. Valid for 5 minutes."

        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(
                    url,
                    auth=(self.account_sid, self.auth_token),
                    data={
                        "To": mobile_number,
                        "From": "+10000000000",  # Replace with Twilio sender number
                        "Body": body,
                    },
                )

            if resp.status_code in (200, 201):
                print(f"[Twilio] OTP sent to {mobile_number}")
                return {"success": True, "message": "OTP dispatched via Twilio"}
            else:
                print(f"[Twilio] API error {resp.status_code}: {resp.text}")
                return {"success": False, "message": f"Twilio API error: {resp.status_code}"}

        except httpx.TimeoutException:
            print(f"[Twilio] Timeout sending OTP to {mobile_number}")
            return {"success": False, "message": "Twilio request timed out"}
        except Exception as e:
            print(f"[Twilio] Unexpected error: {e}")
            return {"success": False, "message": f"Twilio dispatch failed: {e}"}

    def verify_otp_gateway(self, mobile_number: str, otp_code: str) -> dict:
        """
        Twilio does not provide native server-side OTP verification.
        Verification is handled locally by the application database.
        """
        return {"verified": False, "message": "Twilio does not support gateway-side OTP verification. Use local DB verification."}


class MSG91Provider(BaseSMSProvider):
    """
    MSG91 SMS gateway implementation.
    Uses MSG91's streamlined SendOTP and VerifyOTP REST API endpoints.
    Accepts auth_key via constructor (injected by factory from settings).
    """

    def __init__(self, auth_key: str):
        self.auth_key = auth_key
        self.url = "https://control.msg91.com/api/v5/otp"
        self.verify_url = "https://control.msg91.com/api/v5/otp/verify"

    def send_otp(self, mobile_number: str, otp_code: str) -> dict:
        """Send OTP via MSG91 OTP API."""
        # Format the number for MSG91 (strip the '+' symbol as MSG91 expects pure country code + digits)
        clean_mobile = mobile_number.replace("+", "")

        payload = {
            "otp": otp_code,
            "mobile": clean_mobile
        }
        headers = {
            "authkey": self.auth_key,
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(self.url, json=payload, headers=headers, timeout=10)
            if response.status_code in [200, 202]:
                print(f"[MSG91] OTP sent to {mobile_number}")
                return {"success": True, "message": "OTP dispatched via MSG91"}
            else:
                print(f"[MSG91] Error sending OTP: {response.text}")
                raise Exception(f"MSG91 Gateway returned status {response.status_code}")

        except requests.exceptions.Timeout:
            print(f"[MSG91] Timeout sending OTP to {mobile_number}")
            return {"success": False, "message": "MSG91 request timed out"}
        except Exception as e:
            print(f"[MSG91] Unexpected error: {e}")
            return {"success": False, "message": f"MSG91 dispatch failed: {e}"}

    def verify_otp_gateway(self, mobile_number: str, otp_code: str) -> dict:
        """Verify OTP via MSG91's server-side verification endpoint."""
        clean_mobile = mobile_number.replace("+", "")

        try:
            response = requests.get(
                self.verify_url,
                headers={"authkey": self.auth_key},
                params={"mobile": clean_mobile, "otp": otp_code},
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("type") == "success":
                    print(f"[MSG91] OTP verified for {mobile_number}")
                    return {"verified": True, "message": "OTP verified via MSG91"}
                else:
                    return {"verified": False, "message": f"MSG91 verification failed: {data.get('message', 'unknown')}"}
            else:
                return {"verified": False, "message": f"MSG91 verify API error: {response.status_code}"}

        except requests.exceptions.Timeout:
            print(f"[MSG91] Timeout verifying OTP for {mobile_number}")
            return {"verified": False, "message": "MSG91 verify request timed out"}
        except Exception as e:
            print(f"[MSG91] Unexpected error during verification: {e}")
            return {"verified": False, "message": f"MSG91 verification failed: {e}"}

