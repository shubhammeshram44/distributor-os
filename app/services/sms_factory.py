"""
SMS Gateway Factory
====================
Dynamically resolves and returns the correct SMS provider instance
based on the SMS_PROVIDER environment variable.
"""

from app.config import settings
from app.services.sms_base import BaseSMSProvider


def get_sms_gateway() -> BaseSMSProvider:
    """
    Factory method that reads SMS_PROVIDER from environment/settings
    and returns the corresponding provider instance.

    Supported values:
        - "TWILIO"  → TwilioSMSProvider
        - "MSG91"   → MSG91Provider

    Raises:
        ValueError: If SMS_PROVIDER is set to an unsupported vendor string.
    """
    provider_name = settings.SMS_PROVIDER.upper().strip()

    if provider_name == "TWILIO":
        from app.services.sms_providers import TwilioSMSProvider
        return TwilioSMSProvider()

    elif provider_name == "MSG91":
        from app.services.sms_providers import MSG91Provider
        return MSG91Provider()

    else:
        raise ValueError(
            f"Unsupported SMS_PROVIDER: '{provider_name}'. "
            f"Supported values are: TWILIO, MSG91"
        )
