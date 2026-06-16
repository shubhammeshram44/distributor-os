"""
Vendor-Agnostic SMS Provider Abstraction Layer
===============================================
Defines the abstract contract that all SMS gateway implementations must follow.
This ensures application workflows remain decoupled from any specific vendor SDK.
"""

from abc import ABC, abstractmethod


class BaseSMSProvider(ABC):
    """
    Abstract Base Class for SMS gateway providers.
    All vendor implementations (Twilio, MSG91, Exotel, etc.) must subclass this
    and implement the two core authentication methods.
    """

    @abstractmethod
    def send_otp(self, mobile_number: str, otp_code: str) -> dict:
        """
        Dispatch an OTP code to the target mobile number via the provider's API.

        Args:
            mobile_number: The recipient's phone number (E.164 format preferred).
            otp_code: The 6-digit OTP string to deliver.

        Returns:
            A dict with at minimum {"success": bool, "message": str}.
        """
        ...

    @abstractmethod
    def verify_otp_gateway(self, mobile_number: str, otp_code: str) -> dict:
        """
        Verify an OTP code against the provider's server-side verification API,
        if the provider supports native OTP verification (e.g., MSG91).

        Args:
            mobile_number: The phone number that received the OTP.
            otp_code: The OTP code submitted by the user.

        Returns:
            A dict with at minimum {"verified": bool, "message": str}.
        """
        ...
