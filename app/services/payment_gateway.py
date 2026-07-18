# DEPLOYMENT REMINDER:
# After deployment, go to Razorpay Dashboard → Settings → Webhooks → Add:
# - URL: `https://distributor-os-backend.onrender.com/api/v1/payments/razorpay-webhook`
# - Event: `payment_link.paid`
# - Copy webhook secret → add to Render env as `RAZORPAY_WEBHOOK_SECRET`

import razorpay
import os

class PaymentGateway:
    """
    Abstraction layer over Razorpay.
    Swap implementation here without changing callers.
    """
    
    def __init__(self, key_id: str | None = None, key_secret: str | None = None):
        # Use provided keys (from tenant DB) 
        # NO fallback to env vars — if no keys provided, raise immediately
        if not key_id or not key_secret:
            raise ValueError(
                "Razorpay credentials not configured. "
                "Please connect your Razorpay account in Settings → Payments."
            )
        self.client = razorpay.Client(auth=(key_id, key_secret))
        self.mode = "test" if key_id.startswith("rzp_test_") else "live"
    
    def create_payment_link(
        self,
        amount_inr: float,
        customer_name: str,
        customer_phone: str,
        customer_email: str | None,
        description: str,
        reference_id: str,
        expire_by_unix: int | None = None
    ) -> dict:
        """
        Creates a Razorpay payment link.
        Returns dict with keys: id, short_url, url, status
        Amount in INR (not paise) — converted internally.
        """
        payload = {
            "amount": int(amount_inr * 100),  # convert to paise
            "currency": "INR",
            "description": description,
            "reference_id": reference_id,
            "customer": {
                "name": customer_name,
                "contact": customer_phone,
            },
            "notify": {
                "sms": True,
                "email": False
            },
            "reminder_enable": False,  # we handle reminders ourselves
            "callback_url": os.getenv("APP_URL", "https://distributor-os-backend.onrender.com") + "/api/v1/payments/razorpay-webhook",
            "callback_method": "get"
        }
        if customer_email:
            payload["customer"]["email"] = customer_email
        if expire_by_unix:
            payload["expire_by"] = expire_by_unix

        return self.client.payment_link.create(payload)
    
    def fetch_payment_link(self, payment_link_id: str) -> dict:
        return self.client.payment_link.fetch(payment_link_id)
    
    def verify_webhook_signature(self, body: str, signature: str) -> bool:
        secret = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")
        try:
            self.client.utility.verify_webhook_signature(body, signature, secret)
            return True
        except Exception:
            return False
