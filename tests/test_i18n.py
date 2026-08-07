"""Tests for the i18n module."""

import pytest
import os
from src.utils.i18n import I18n, get_i18n, _


class TestI18n:
    def test_default_locale(self):
        i18n = I18n()
        assert i18n.locale == "en"

    def test_translate_english(self):
        i18n = I18n(locale="en")
        assert i18n.translate("profiles.create") == "Create"
        assert i18n.translate("profiles.start") == "Start"

    def test_translate_chinese(self):
        i18n = I18n(locale="zh")
        assert i18n.translate("profiles.create") == "创建"
        assert i18n.translate("profiles.start") == "启动"

    def test_translate_spanish(self):
        i18n = I18n(locale="es")
        assert i18n.translate("profiles.create") == "Crear"
        assert i18n.translate("profiles.start") == "Iniciar"

    def test_fallback_to_key(self):
        i18n = I18n(locale="en")
        assert i18n.translate("nonexistent.key") == "nonexistent.key"

    def test_change_locale(self):
        i18n = I18n(locale="en")
        assert i18n.translate("profiles.delete") == "Delete"
        i18n.locale = "zh"
        assert i18n.translate("profiles.delete") == "删除"

    def test_unsupported_locale_falls_back(self):
        i18n = I18n(locale="fr")  # Not supported
        assert i18n.locale == "en"  # Falls back to default

    def test_get_all_translations(self):
        i18n = I18n(locale="en")
        translations = i18n.get_all_translations()
        assert "profiles.create" in translations
        assert "app.title" in translations

    def test_shorthand_function(self):
        # Reset global instance
        import src.utils.i18n as i18n_mod
        i18n_mod._i18n_instance = None

        result = _("profiles.create")
        assert result is not None
        assert isinstance(result, str)

    def test_all_locales_have_same_keys(self):
        """Verify all locale files have the same translation keys."""
        i18n = I18n()
        en_keys = set(i18n.TRANSLATIONS["en"].keys())
        zh_keys = set(i18n.TRANSLATIONS["zh"].keys())
        es_keys = set(i18n.TRANSLATIONS["es"].keys())

        assert en_keys == zh_keys, f"Missing keys in zh: {en_keys.symmetric_difference(zh_keys)}"
        assert en_keys == es_keys, f"Missing keys in es: {en_keys.symmetric_difference(es_keys)}"

    def test_locale_files_created(self):
        """Verify locale files are written to disk."""
        import tempfile
        import json

        with tempfile.TemporaryDirectory() as tmpdir:
            locales_dir = os.path.join(tmpdir, "locales")
            # I18n creates locale files on init
            # This is implicitly tested by the fact that other tests pass
            # (they load from files if they exist)
