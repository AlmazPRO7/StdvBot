"""
Bot Metrics - сбор и хранение статистики использования бота.
"""
import json
import logging
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


class BotMetrics:
    """
    Трекер метрик использования бота.
    Сохраняет данные в JSON с разбивкой по дням.
    """

    def __init__(self, storage_path: str = "data/metrics.json"):
        self.storage_path = Path(storage_path)
        self.data: Dict = {}
        self._load()

    def _load(self):
        """Загрузка данных из файла"""
        if self.storage_path.exists():
            try:
                self.data = json.loads(self.storage_path.read_text())
                logger.info(f"Metrics loaded: {len(self.data.get('daily', {}))} days of data")
            except Exception as e:
                logger.error(f"Failed to load metrics: {e}")
                self._init_empty()
        else:
            self._init_empty()

    def _init_empty(self):
        """Инициализация пустой структуры"""
        self.data = {
            "total": {
                "requests": 0,
                "text_queries": 0,
                "photo_analyses": 0,
                "voice_messages": 0,
                "errors": 0,
                "rate_limited": 0
            },
            "users": {},  # user_id -> {"first_seen": date, "requests": count}
            "daily": {}   # date -> {metrics}
        }

    def _save(self):
        """Сохранение данных в файл"""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            self.storage_path.write_text(json.dumps(self.data, indent=2, ensure_ascii=False))
        except Exception as e:
            logger.error(f"Failed to save metrics: {e}")

    def _today(self) -> str:
        """Текущая дата в формате YYYY-MM-DD"""
        return date.today().isoformat()

    def _ensure_daily(self, day: str = None):
        """Создаёт структуру для дня если не существует"""
        day = day or self._today()
        if day not in self.data["daily"]:
            self.data["daily"][day] = {
                "requests": 0,
                "text_queries": 0,
                "photo_analyses": 0,
                "voice_messages": 0,
                "errors": 0,
                "rate_limited": 0,
                "unique_users": []
            }

    def track_request(
        self,
        user_id: int,
        request_type: str = "text",
        success: bool = True
    ):
        """
        Трекинг запроса.

        Args:
            user_id: ID пользователя Telegram
            request_type: "text", "photo", "voice"
            success: Успешно ли обработан
        """
        user_id = str(user_id)
        today = self._today()
        self._ensure_daily(today)

        # Total
        self.data["total"]["requests"] += 1

        # Daily
        self.data["daily"][today]["requests"] += 1

        # По типу
        type_map = {
            "text": "text_queries",
            "photo": "photo_analyses",
            "voice": "voice_messages"
        }
        if request_type in type_map:
            self.data["total"][type_map[request_type]] += 1
            self.data["daily"][today][type_map[request_type]] += 1

        # Ошибки
        if not success:
            self.data["total"]["errors"] += 1
            self.data["daily"][today]["errors"] += 1

        # Пользователи
        if user_id not in self.data["users"]:
            self.data["users"][user_id] = {
                "first_seen": today,
                "requests": 0,
                "last_seen": today
            }
        self.data["users"][user_id]["requests"] += 1
        self.data["users"][user_id]["last_seen"] = today

        # Уникальные за день
        if user_id not in self.data["daily"][today]["unique_users"]:
            self.data["daily"][today]["unique_users"].append(user_id)

        self._save()
        logger.debug(f"Tracked {request_type} request from user {user_id}")

    def track_rate_limited(self, user_id: int):
        """Трекинг заблокированного запроса (лимит)"""
        today = self._today()
        self._ensure_daily(today)

        self.data["total"]["rate_limited"] += 1
        self.data["daily"][today]["rate_limited"] += 1
        self._save()

        logger.info(f"Rate limited request from user {user_id}")

    def get_summary(self) -> Dict:
        """Общая статистика"""
        return {
            "total": self.data["total"].copy(),
            "unique_users": len(self.data["users"]),
            "days_tracked": len(self.data["daily"])
        }

    def get_today_stats(self) -> Dict:
        """Статистика за сегодня"""
        today = self._today()
        self._ensure_daily(today)

        daily = self.data["daily"][today].copy()
        daily["unique_users_count"] = len(daily.get("unique_users", []))
        del daily["unique_users"]  # Не показываем список ID

        return {
            "date": today,
            **daily
        }

    def get_user_stats(self, user_id: int) -> Optional[Dict]:
        """Статистика конкретного пользователя"""
        user_id = str(user_id)
        if user_id not in self.data["users"]:
            return None
        return self.data["users"][user_id].copy()

    def get_report(self, days: int = 7) -> str:
        """
        Текстовый отчёт за последние N дней.
        """
        lines = ["📊 *Статистика бота*\n"]

        # Общая статистика
        summary = self.get_summary()
        lines.append(f"*Всего:*")
        lines.append(f"• Запросов: {summary['total']['requests']}")
        lines.append(f"• Уникальных пользователей: {summary['unique_users']}")
        lines.append(f"• Текстовых: {summary['total']['text_queries']}")
        lines.append(f"• Фото: {summary['total']['photo_analyses']}")
        lines.append(f"• Голосовых: {summary['total']['voice_messages']}")
        lines.append(f"• Ошибок: {summary['total']['errors']}")
        lines.append(f"• Заблокировано (лимит): {summary['total']['rate_limited']}")

        # За сегодня
        today_stats = self.get_today_stats()
        lines.append(f"\n*Сегодня ({today_stats['date']}):*")
        lines.append(f"• Запросов: {today_stats['requests']}")
        lines.append(f"• Уникальных: {today_stats['unique_users_count']}")

        return "\n".join(lines)


# Глобальный экземпляр
bot_metrics = BotMetrics()
