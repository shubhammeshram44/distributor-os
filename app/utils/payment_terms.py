import re
import logging

logger = logging.getLogger("uvicorn.error")

def parse_credit_days(payment_terms: str, customer_name: str = "Unknown", tenant_name: str = "Unknown") -> int:
    # DATA-MODELING GAP WARNING:
    # payment_terms being stored as a free-text string (e.g. "0-15 Days", "Net 30") is a data-modeling gap.
    # It would be cleaner to store this as a structured integer column (e.g. credit_days: int) directly on the customer model.
    # This regex parsing is a robust workaround, but the schema should be fixed later.

    if not payment_terms:
        logger.warning(
            "Empty payment terms encountered for Customer: %s, Tenant: %s. Defaulting to 30 days.",
            customer_name, tenant_name
        )
        return 30

    match = re.search(r'\d+', payment_terms)
    if match:
        return int(match.group())

    logger.warning(
        "Could not parse credit days from payment_terms '%s' for Customer: %s, Tenant: %s. Defaulting to 30 days.",
        payment_terms, customer_name, tenant_name
    )
    return 30
