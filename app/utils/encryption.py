from cryptography.fernet import Fernet
import os
import base64

def get_fernet():
    key = os.getenv("ENCRYPTION_KEY")
    if not key:
        raise ValueError("ENCRYPTION_KEY env var not set")
    if isinstance(key, str):
        key = key.strip()
    return Fernet(key.encode() if isinstance(key, str) else key)

def encrypt_secret(plain: str) -> str:
    return get_fernet().encrypt(plain.encode()).decode()

def decrypt_secret(encrypted: str) -> str:
    return get_fernet().decrypt(encrypted.encode()).decode()
