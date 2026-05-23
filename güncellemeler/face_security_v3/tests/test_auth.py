"""
auth/auth_manager.py birim testleri.
"""
import json
import pytest
from auth.auth_manager import AuthManager


@pytest.fixture
def auth(tmp_path):
    config_file = str(tmp_path / "auth_config.json")
    return AuthManager(config_path=config_file)


class TestAuthManager:
    def test_default_pin_works(self, auth):
        assert auth.verify_pin("1234") is True

    def test_wrong_pin_fails(self, auth):
        assert auth.verify_pin("0000") is False

    def test_is_authenticated_after_success(self, auth):
        auth.verify_pin("1234")
        assert auth.is_authenticated is True

    def test_not_authenticated_after_failure(self, auth):
        auth.verify_pin("wrong")
        assert auth.is_authenticated is False

    def test_change_pin(self, auth):
        ok = auth.change_pin("1234", "5678")
        assert ok is True
        assert auth.verify_pin("5678") is True
        assert auth.verify_pin("1234") is False

    def test_change_pin_wrong_old(self, auth):
        ok = auth.change_pin("wrong", "5678")
        assert ok is False

    def test_change_pin_too_short(self, auth):
        ok = auth.change_pin("1234", "12")
        assert ok is False

    def test_logout(self, auth):
        auth.verify_pin("1234")
        auth.logout()
        assert auth.is_authenticated is False

    def test_config_persisted(self, tmp_path):
        config_file = str(tmp_path / "auth.json")
        auth1 = AuthManager(config_path=config_file)
        auth1.change_pin("1234", "9999")

        # Yeni instance aynı dosyayı okusun
        auth2 = AuthManager(config_path=config_file)
        assert auth2.verify_pin("9999") is True
        assert auth2.verify_pin("1234") is False
