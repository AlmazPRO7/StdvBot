import sys
import os
sys.path.insert(0, os.getcwd())

from src.prompts import ANALYST_SYSTEM_PROMPT, SUPPORT_AGENT_SYSTEM_PROMPT, VISION_SYSTEM_PROMPT, UNIVERSAL_AGENT_SYSTEM_PROMPT
from prompt_engineering.prompt_manager import PromptManager

manager = PromptManager()

print("🚀 Migrating prompts to Registry...")

# 1. Analyst
manager.create_prompt(
    "analyst_v1", 
    ANALYST_SYSTEM_PROMPT, 
    description="Core analyst for intent classification (JSON)",
    author="Gemini"
)
print("✅ Analyst Saved")

# 2. Support
manager.create_prompt(
    "support_v1", 
    SUPPORT_AGENT_SYSTEM_PROMPT, 
    description="Escalation handler (complaints)",
    author="Gemini"
)
print("✅ Support Saved")

# 3. Vision
manager.create_prompt(
    "vision_v5_stable", 
    VISION_SYSTEM_PROMPT, 
    description="Product search with freeTextSearch and NO BRAND for small parts",
    author="Gemini"
)
print("✅ Vision Saved")

# 4. Universal Voice
manager.create_prompt(
    "universal_voice_v1", 
    UNIVERSAL_AGENT_SYSTEM_PROMPT, 
    description="Voice handler with Shopping List capabilities",
    author="Gemini"
)
print("✅ Universal Voice Saved")

print("\n🎉 Migration Complete! Use './prompt_engineering_cli.py prompt list' to verify.")
