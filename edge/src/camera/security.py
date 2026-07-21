"""Credential encryption module for the AERA Camera Management System.

This module implements a pure-Python symmetric XOR cipher base64-encoded to secure
camera connection passwords in the database without external dependencies.
"""

import base64
import os

# Unique encryption key sourced from system environments with a fallback
SECRET_KEY = os.environ.get("AERA_SECRET_KEY", "aera-default-encryption-secret-key-12345")


def encrypt_password(password: str) -> str:
    """Encrypt a password string into a base64 encoded XOR string.

    Args:
        password: Raw password string.

    Returns:
        Base64-encoded encrypted string.
    """
    if not password:
        return ""
    
    key = SECRET_KEY
    encrypted_chars = [
        chr(ord(c) ^ ord(key[i % len(key)]))
        for i, c in enumerate(password)
    ]
    encrypted_str = "".join(encrypted_chars)
    return base64.b64encode(encrypted_str.encode("utf-8")).decode("utf-8")


def decrypt_password(encrypted_base64: str) -> str:
    """Decrypt a base64 encoded XOR string back to the original password.

    Args:
        encrypted_base64: Encrypted password string.

    Returns:
        Decrypted plaintext password string.
    """
    if not encrypted_base64:
        return ""
    
    try:
        decoded_bytes = base64.b64decode(encrypted_base64.encode("utf-8"))
        decoded_str = decoded_bytes.decode("utf-8")
        key = SECRET_KEY
        decrypted_chars = [
            chr(ord(c) ^ ord(key[i % len(key)]))
            for i, c in enumerate(decoded_str)
        ]
        return "".join(decrypted_chars)
    except Exception:
        return ""
