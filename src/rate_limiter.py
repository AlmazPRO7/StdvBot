"""
Rate Limiter - ограничение запросов на пользователя.
По умолчанию: 30 запросов в сутки на пользователя.
"""
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Tuple

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Суточный лимит запросов на пользователя.
    Данные сохраняются в JSON для персистентности между перезапусками.
    """

    def __init__(
        self,
        max_requests: int = 30,
        storage_path: str = "data/rate_limits.json"
    ):
        self.max_requests = max_requests
        self.storage_path = Path(storage_path)
        self.users: Dict[int, Dict] = {}  # user_id -> {"count": int, "reset_at": str}
        self._load()

    def _load(self):
        """Загрузка данных из файла"""
        if self.storage_path.exists():
            try:
                data = json.loads(self.storage_path.read_text())
                # Конвертируем ключи обратно в int
                self.users = {int(k): v for k, v in data.items()}
                logger.info(f"Rate limits loaded: {len(self.users)} users")
            except Exception as e:
                logger.error(f"Failed to load rate limits: {e}")
                self.users = {}

    def _save(self):
        """Сохранение данных в файл"""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            self.storage_path.write_text(json.dumps(self.users, indent=2, ensure_ascii=False))
        except Exception as e:
            logger.error(f"Failed to save rate limits: {e}")

    def _get_reset_time(self) -> str:
        """Время сброса лимита (полночь следующего дня)"""
        tomorrow = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        return tomorrow.isoformat()

    def _is_expired(self, reset_at: str) -> bool:
        """Проверка: истёк ли период лимита"""
        try:
            reset_time = datetime.fromisoformat(reset_at)
            return datetime.now() >= reset_time
        except:
            return True

    def check(self, user_id: int) -> Tuple[bool, int]:
        """
        Проверяет, может ли пользователь сделать запрос.

        Returns:
            (is_allowed, remaining) - можно ли, сколько осталось
        """
        user_id = int(user_id)

        # Новый пользователь или истёк лимит
        if user_id not in self.users or self._is_expired(self.users[user_id]["reset_at"]):
            self.users[user_id] = {
                "count": 0,
                "reset_at": self._get_reset_time()
            }

        current = self.users[user_id]["count"]
        remaining = self.max_requests - current

        return (remaining > 0, max(0, remaining))

    def consume(self, user_id: int) -> Tuple[bool, int]:
        """
        Использует один запрос из лимита.

        Returns:
            (success, remaining) - успешно ли, сколько осталось
        """
        user_id = int(user_id)
        is_allowed, remaining = self.check(user_id)

        if not is_allowed:
            return (False, 0)

        self.users[user_id]["count"] += 1
        remaining = self.max_requests - self.users[user_id]["count"]
        self._save()

        logger.info(f"Rate limit: user {user_id} used request, {remaining} remaining")
        return (True, remaining)

    def get_status(self, user_id: int) -> Dict:
        """Получить статус лимита пользователя"""
        user_id = int(user_id)
        is_allowed, remaining = self.check(user_id)

        reset_at = self.users.get(user_id, {}).get("reset_at", self._get_reset_time())

        return {
            "user_id": user_id,
            "remaining": remaining,
            "limit": self.max_requests,
            "used": self.max_requests - remaining,
            "reset_at": reset_at,
            "is_allowed": is_allowed
        }

    def get_time_until_reset(self, user_id: int) -> str:
        """Человекочитаемое время до сброса"""
        status = self.get_status(user_id)
        try:
            reset_time = datetime.fromisoformat(status["reset_at"])
            delta = reset_time - datetime.now()

            if delta.total_seconds() <= 0:
                return "сейчас"

            hours = int(delta.total_seconds() // 3600)
            minutes = int((delta.total_seconds() % 3600) // 60)

            if hours > 0:
                return f"{hours}ч {minutes}мин"
            return f"{minutes}мин"
        except:
            return "скоро"


# Глобальный экземпляр
rate_limiter = RateLimiter(max_requests=30)
