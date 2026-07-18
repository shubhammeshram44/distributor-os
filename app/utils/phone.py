import re

def normalize_phone_number(phone_str: str) -> str:
    """
    Normalizes a phone number to standard E.164 format (+91XXXXXXXXXX).
    If it's already in E.164, returns it. Strips spaces, dashes, parentheses.
    """
    if not phone_str:
        return ""
    
    # Handle WhatsApp JID format (e.g. 919199153059@s.whatsapp.net)
    if "@" in phone_str:
        phone_str = phone_str.split("@")[0]
        
    # Strip all non-digit characters
    digits = re.sub(r"\D", "", phone_str)
    
    # Standard 10 digits
    if len(digits) == 10:
        return f"+91{digits}"
    # 12 digits starting with 91
    if len(digits) == 12 and digits.startswith("91"):
        return f"+91{digits[2:]}"
    
    # Otherwise, return with a leading '+'
    if phone_str.startswith("+") or not digits:
        return f"+{digits}" if digits else ""
    return f"+{digits}"


def get_phone_number_variants(phone_str: str) -> list[str]:
    """
    Generates potential string representation variants of a phone number:
    - E.164 normalized: +91XXXXXXXXXX
    - Stripped leading '+': 91XXXXXXXXXX
    - 10-digit suffix: XXXXXXXXXX
    - Original input string (stripped)
    """
    if not phone_str:
        return []
    
    normalized = normalize_phone_number(phone_str)
    if not normalized:
        return []
        
    variants = {normalized}
    
    # Strip leading '+'
    stripped = normalized.lstrip("+")
    variants.add(stripped)
    
    # Only keep digits
    digits = re.sub(r"\D", "", normalized)
    if digits:
        variants.add(digits)
        # 10 digit suffix if applicable
        if len(digits) >= 10:
            variants.add(digits[-10:])
            
    # Also add original phone_str
    variants.add(phone_str.strip())
    
    return sorted(list(variants))

