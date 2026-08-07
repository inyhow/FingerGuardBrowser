"""AES-256 encryption for sensitive profile data (proxy credentials, cookies).

Uses OS keychain for master key storage when available:
- Windows: Credential Manager (via keyring)
- macOS: Keychain (via keyring)
- Linux: Secret Service (via keyring)

Falls back to a password-derived key if keyring is unavailable.
"""

import base64
import hashlib
import os
import platform
from typing import Optional
from loguru import logger

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    logger.warning("cryptography package not installed — encryption disabled")

try:
    import keyring
    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False
    logger.info("keyring package not installed — using password-based key derivation")

KEYRING_SERVICE = "FingerGuardBrowser"
KEYRING_KEY_NAME = "master_key"


class CryptoManager:
    """Encrypt and decrypt sensitive data using AES-256 (Fernet symmetric encryption)."""

    def __init__(self, master_password: str = None):
        self._fernet: Optional[Fernet] = None
        self._master_password = master_password

        if not CRYPTO_AVAILABLE:
            logger.warning("Encryption disabled — install 'cryptography' package")
            return

        self._fernet = self._init_fernet(master_password)

    def _init_fernet(self, password: str = None) -> Optional[Fernet]:
        """Initialize Fernet cipher with a key from password or keyring.

        Priority: explicit password > OS keychain > ephemeral key.
        """
        key = None

        # Explicit password takes priority — ensures different passwords
        # produce different keys (used for profile-level encryption)
        if password:
            salt = b"FingerGuardBrowser_salt_v1"
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100_000,
            )
            derived = kdf.derive(password.encode())
            key = base64.urlsafe_b64encode(derived).decode()
            logger.info("Using password-derived encryption key")
        elif KEYRING_AVAILABLE:
            try:
                key = keyring.get_password(KEYRING_SERVICE, KEYRING_KEY_NAME)
                if key is None:
                    # Generate and store a new key
                    key = Fernet.generate_key().decode()
                    keyring.set_password(KEYRING_SERVICE, KEYRING_KEY_NAME, key)
                    logger.info("Generated and stored new master key in OS keychain")
            except Exception as e:
                logger.warning(f"Keychain access failed: {e}")

        if key is None:
            # No keyring, no password — generate ephemeral key (not persisted)
            key = Fernet.generate_key().decode()
            logger.warning("No keychain or password — using ephemeral key (data won't persist across restarts)")

        return Fernet(key.encode())

    @property
    def is_available(self) -> bool:
        """Whether encryption is available."""
        return self._fernet is not None

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a string, return base64-encoded ciphertext."""
        if not self.is_available:
            return plaintext
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt a base64-encoded ciphertext string."""
        if not self.is_available:
            return ciphertext
        try:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            return ciphertext

    def encrypt_dict(self, data: dict) -> str:
        """Encrypt a dictionary (serialized as JSON)."""
        import json
        return self.encrypt(json.dumps(data))

    def decrypt_dict(self, ciphertext: str) -> dict:
        """Decrypt a ciphertext back to dictionary."""
        import json
        plaintext = self.decrypt(ciphertext)
        try:
            return json.loads(plaintext)
        except json.JSONDecodeError:
            return {}

    def mask_sensitive(self, data: dict, fields: list = None) -> dict:
        """Mask sensitive fields in a dict for API responses.

        Default sensitive fields: password, proxy, credentials, cookie, token, secret.
        """
        if fields is None:
            fields = ["password", "proxy", "credentials", "cookie", "token", "secret"]

        masked = {}
        for key, value in data.items():
            if any(sensitive in key.lower() for sensitive in fields):
                if value:
                    masked[key] = "***MASKED***"
                else:
                    masked[key] = value
            elif isinstance(value, dict):
                masked[key] = self.mask_sensitive(value, fields)
            else:
                masked[key] = value
        return masked
