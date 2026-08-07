"""Tests for the encryption and security module."""

import pytest
from src.security.crypto import CryptoManager


class TestCryptoManager:
    def test_encrypt_decrypt_string(self):
        crypto = CryptoManager(master_password="test_password")
        if not crypto.is_available:
            pytest.skip("cryptography package not installed")

        plaintext = "secret_proxy_credentials_123"
        encrypted = crypto.encrypt(plaintext)
        assert encrypted != plaintext
        assert crypto.decrypt(encrypted) == plaintext

    def test_encrypt_decrypt_dict(self):
        crypto = CryptoManager(master_password="test_password")
        if not crypto.is_available:
            pytest.skip("cryptography package not installed")

        data = {"proxy": "socks5://user:pass@host:1080", "name": "test"}
        encrypted = crypto.encrypt_dict(data)
        assert isinstance(encrypted, str)
        decrypted = crypto.decrypt_dict(encrypted)
        assert decrypted == data

    def test_mask_sensitive_fields(self):
        crypto = CryptoManager(master_password="test")
        data = {
            "name": "profile1",
            "password": "secret123",
            "proxy": "socks5://host:port",
            "tags": ["amazon"],
            "nested": {"token": "abc", "safe": "ok"},
        }
        masked = crypto.mask_sensitive(data)
        assert masked["name"] == "profile1"
        assert masked["password"] == "***MASKED***"
        assert masked["proxy"] == "***MASKED***"
        assert masked["tags"] == ["amazon"]
        assert masked["nested"]["token"] == "***MASKED***"
        assert masked["nested"]["safe"] == "ok"

    def test_mask_empty_sensitive_field(self):
        crypto = CryptoManager(master_password="test")
        data = {"password": "", "name": "test"}
        masked = crypto.mask_sensitive(data)
        assert masked["password"] == ""

    def test_mask_custom_fields(self):
        crypto = CryptoManager(master_password="test")
        data = {"api_key": "12345", "name": "test"}
        masked = crypto.mask_sensitive(data, fields=["api_key"])
        assert masked["api_key"] == "***MASKED***"
        assert masked["name"] == "test"

    def test_different_passwords_produce_different_keys(self):
        crypto1 = CryptoManager(master_password="password1")
        crypto2 = CryptoManager(master_password="password2")
        if not crypto1.is_available or not crypto2.is_available:
            pytest.skip("cryptography package not installed")

        encrypted = crypto1.encrypt("test_data")
        # Decrypting with a different key should fail (return ciphertext)
        decrypted = crypto2.decrypt(encrypted)
        assert decrypted != "test_data"

    def test_encrypt_empty_string(self):
        crypto = CryptoManager(master_password="test")
        if not crypto.is_available:
            pytest.skip("cryptography package not installed")

        encrypted = crypto.encrypt("")
        decrypted = crypto.decrypt(encrypted)
        assert decrypted == ""
