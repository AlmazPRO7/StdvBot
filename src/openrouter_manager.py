import requests
import logging
import random
import time
from src.config import Config

logger = logging.getLogger(__name__)

class OpenRouterManager:
    def __init__(self):
        self.keys = Config.API_KEYS.copy()
        random.shuffle(self.keys)
        self.current_key_index = 0
        
        logger.info(f"🔑 Loaded {len(self.keys)} OpenRouter keys")
        # ТОЛЬКО ЭТА МОДЕЛЬ
        self.target_model = "google/gemini-2.0-flash-exp:free"

    def get_current_headers(self):
        return {
            "Authorization": f"Bearer {self.keys[self.current_key_index]}",
            "HTTP-Referer": Config.SITE_URL,
            "X-Title": Config.SITE_NAME,
            "Content-Type": "application/json"
        }

    def rotate_key(self):
        prev_key = self.keys[self.current_key_index][:10] + "..."
        self.current_key_index = (self.current_key_index + 1) % len(self.keys)
        new_key = self.keys[self.current_key_index][:10] + "..."
        logger.warning(f"🔄 Rotating API Key: {prev_key} -> {new_key}")
        # Даем небольшую паузу при смене ключа, чтобы не спамить
        time.sleep(2)

    def get_best_free_model(self):
        # Просто возвращаем целевую модель, не тратим время на поиск
        return self.target_model