"""
Unit tests for config.py module.
Tests graceful degradation and validation.
"""

import pytest
import os
import sys
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestConfigValidation:
    """Test Config validation and graceful degradation."""

    def test_validate_returns_dict(self):
        """Test that validate() returns a dict with required keys."""
        from src.config import Config

        result = Config.validate()

        assert isinstance(result, dict)
        assert "valid" in result
        assert "warnings" in result
        assert "errors" in result
        assert "mode" in result
        assert "available_providers" in result

    def test_validate_no_crash_without_keys(self):
        """Test that validation doesn't crash even without API keys."""
        from src.config import Config

        # This should not raise any exceptions
        try:
            result = Config.validate()
            assert isinstance(result, dict)
        except Exception as e:
            pytest.fail(f"Config.validate() raised exception: {e}")

    def test_get_effective_provider_auto(self):
        """Test effective provider determination in auto mode."""
        from src.config import Config

        with patch.object(Config, 'AI_PROVIDER', 'auto'):
            provider = Config.get_effective_provider()
            assert provider in ["auto", "gemini", "openrouter"]

    def test_get_effective_provider_gemini(self):
        """Test effective provider when set to gemini."""
        from src.config import Config

        with patch.object(Config, 'AI_PROVIDER', 'gemini'):
            provider = Config.get_effective_provider()
            assert provider == "gemini"

    def test_get_effective_provider_fallback(self):
        """Test fallback when openrouter requested but unavailable."""
        from src.config import Config

        with patch.object(Config, 'AI_PROVIDER', 'openrouter'):
            with patch.object(Config, 'API_KEYS', []):
                provider = Config.get_effective_provider()
                assert provider == "gemini"  # Should fallback

    def test_gemini_available_without_key(self):
        """Test that Gemini is available via OAuth ADC without API key."""
        from src.config import Config

        # GEMINI_AVAILABLE should be True due to OAuth ADC fallback
        assert Config.GEMINI_AVAILABLE is True

    def test_print_status_no_crash(self):
        """Test that print_status() doesn't crash."""
        from src.config import Config

        try:
            Config.print_status()
        except Exception as e:
            pytest.fail(f"Config.print_status() raised exception: {e}")


class TestConfigEnvironment:
    """Test Config environment variable handling."""

    def test_ai_provider_default(self):
        """Test default AI provider."""
        from src.config import Config

        # Default should be "auto"
        assert Config.AI_PROVIDER in ["auto", "gemini", "openrouter"]

    def test_model_name_default(self):
        """Test default model name."""
        from src.config import Config

        # Should have a default model
        assert Config.MODEL_NAME is not None
        assert len(Config.MODEL_NAME) > 0
