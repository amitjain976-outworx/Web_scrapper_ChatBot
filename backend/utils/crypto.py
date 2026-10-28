import base64
import os
from cryptography.fernet import Fernet, InvalidToken
from dotenv import load_dotenv
load_dotenv()

from utils.logger import get_logger

logger = get_logger(__name__)

# =====================================================
# ENCRYPTION KEY MANAGEMENT
# =====================================================

_ENV_KEY_NAME = "CRYPTO_SECRET_KEY"


def _load_or_fail_key() -> bytes:
    """
    Load encryption key from environment.
    Must be a base64-encoded 32-byte key.
    """
    key = os.getenv(_ENV_KEY_NAME)

    if not key:
        raise RuntimeError(
            f"{_ENV_KEY_NAME} not found in environment. "
            "Generate one using Fernet.generate_key()."
        )

    try:
        return key.encode()
    except Exception as e:
        raise RuntimeError("Invalid CRYPTO_SECRET_KEY format") from e


# Singleton Fernet instance
_FERNET = Fernet(_load_or_fail_key())


# =====================================================
# PUBLIC API
# =====================================================

def encrypt_secret(plain_text: str) -> str:
    """
    Encrypt sensitive value (password, token).
    Returns base64 string safe for DB storage.
    """
    if not plain_text:
        raise ValueError("Cannot encrypt empty secret")

    token = _FERNET.encrypt(plain_text.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_secret(encrypted_text: str) -> str:
    """
    Decrypt secret retrieved from DB.
    """
    if not encrypted_text:
        raise ValueError("Cannot decrypt empty value")

    try:
        decrypted = _FERNET.decrypt(encrypted_text.encode("utf-8"))
        return decrypted.decode("utf-8")
    except InvalidToken:
        logger.error("Failed to decrypt secret: invalid token")
        raise RuntimeError("Invalid encrypted secret")
