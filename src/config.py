"""
Configuration module with graceful degradation support.
Handles missing API keys without crashing.
"""
import os
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class Config:
    """
    Application configuration with validation and graceful degradation.

    Supports three modes:
    - auto: Gemini primary → OpenRouter fallback (RECOMMENDED)
    - gemini: Only Gemini Direct API
    - openrouter: Only OpenRouter
    """

    # --- OPENROUTER SETTINGS ---
    KEYS_STRING = os.getenv("OPENROUTER_API_KEYS", "")
    API_KEYS = [k.strip() for k in KEYS_STRING.split(",") if k.strip()]

    SITE_URL = os.getenv("SITE_URL", "https://github.com")
    SITE_NAME = os.getenv("SITE_NAME", "ConstructionAI")
    BASE_URL = "https://openrouter.ai/api/v1"

    # --- GOOGLE DIRECT SETTINGS ---
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp")

    # Build API URL only if key exists
    if GEMINI_API_KEY:
        API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={GEMINI_API_KEY}"
    else:
        API_URL = None

    # Legacy alias
    API_KEY = GEMINI_API_KEY

    # --- PROVIDER SELECTION ---
    AI_PROVIDER = os.getenv("AI_PROVIDER", "auto")

    # --- TELEGRAM ---
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

    # --- ROLES ---
    ADMIN_USER = os.getenv("ADMIN_USERNAME", "@admin")
    CLIENT_USER = os.getenv("CLIENT_USERNAME", "@client")
    MANAGER_USER = os.getenv("MANAGER_USERNAME", "@manager")

    # --- VALIDATION FLAGS ---
    OPENROUTER_AVAILABLE = bool(API_KEYS)
    GEMINI_AVAILABLE = bool(GEMINI_API_KEY) or True  # OAuth ADC doesn't need key
    TELEGRAM_AVAILABLE = bool(TELEGRAM_TOKEN)

    @classmethod
    def validate(cls) -> dict:
        """
        Validate configuration and return status.
        Does NOT raise exceptions - returns validation results.

        Returns:
            dict with keys: valid, warnings, errors, mode
        """
        result = {
            "valid": True,
            "warnings": [],
            "errors": [],
            "mode": cls.AI_PROVIDER,
            "available_providers": []
        }

        # Check OpenRouter
        if cls.API_KEYS:
            result["available_providers"].append("openrouter")
            logger.info(f"✅ OpenRouter: {len(cls.API_KEYS)} API key(s) configured")
        else:
            result["warnings"].append("OpenRouter API keys not found - OpenRouter disabled")
            logger.warning("⚠️ OpenRouter API keys not found")

        # Check Gemini (OAuth ADC or API key)
        # Note: OAuth ADC works without explicit API key
        result["available_providers"].append("gemini")
        if cls.GEMINI_API_KEY:
            logger.info("✅ Gemini: API key configured")
        else:
            logger.info("✅ Gemini: Using OAuth ADC (no API key needed)")

        # Check Telegram
        if not cls.TELEGRAM_TOKEN:
            result["warnings"].append("Telegram token not found - bot will not start")
            logger.warning("⚠️ TELEGRAM_BOT_TOKEN not found")
        else:
            logger.info("✅ Telegram: Token configured")

        # Validate provider selection
        if cls.AI_PROVIDER == "openrouter" and not cls.API_KEYS:
            result["errors"].append("AI_PROVIDER=openrouter but no API keys found")
            result["valid"] = False

        if cls.AI_PROVIDER == "auto" and not cls.API_KEYS:
            result["warnings"].append("AI_PROVIDER=auto but OpenRouter unavailable - Gemini only mode")
            result["mode"] = "gemini"

        # Summary
        if result["errors"]:
            logger.error(f"❌ Configuration errors: {result['errors']}")

        return result

    @classmethod
    def get_effective_provider(cls) -> str:
        """
        Returns the effective provider based on availability.
        Falls back gracefully if configured provider is unavailable.
        """
        if cls.AI_PROVIDER == "openrouter":
            if cls.API_KEYS:
                return "openrouter"
            else:
                logger.warning("OpenRouter requested but unavailable, falling back to Gemini")
                return "gemini"

        if cls.AI_PROVIDER == "gemini":
            return "gemini"

        # Auto mode
        return "auto"

    @classmethod
    def print_status(cls):
        """Print configuration status to console."""
        print("\n" + "="*60)
        print("🔧 CONFIGURATION STATUS")
        print("="*60)

        validation = cls.validate()

        print(f"\n📡 AI Provider: {validation['mode']}")
        print(f"   Available: {', '.join(validation['available_providers'])}")

        if validation['warnings']:
            print(f"\n⚠️ Warnings:")
            for w in validation['warnings']:
                print(f"   - {w}")

        if validation['errors']:
            print(f"\n❌ Errors:")
            for e in validation['errors']:
                print(f"   - {e}")

        print(f"\n✅ Valid: {validation['valid']}")
        print("="*60 + "\n")


# Auto-validate on import (non-blocking)
_validation = Config.validate()
if not _validation["valid"]:
    logger.error("Configuration validation failed - some features may not work")
