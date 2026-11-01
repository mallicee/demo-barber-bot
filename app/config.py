"""Настройки бота. Все секреты читаются из файла .env в корне проекта."""

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv

# Корень проекта (папка, где лежит bot.py)
BASE_DIR = Path(__file__).resolve().parent.parent

# Загружаем переменные из .env в окружение
load_dotenv(BASE_DIR / ".env")


@dataclass(frozen=True)
class Config:
    bot_token: str
    admin_id: int | None  # None, если ADMIN_ID ещё не указан
    timezone: ZoneInfo
    db_path: Path


def _stop(message: str) -> None:
    """Понятно сообщаем об ошибке настройки и завершаем программу."""
    sys.exit(f"\n[Ошибка настройки] {message}\n")


def load_config() -> Config:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        _stop(
            "Не найден BOT_TOKEN. Создайте файл .env рядом с bot.py "
            "(образец: .env.example) и впишите туда токен от @BotFather."
        )

    admin_raw = os.getenv("ADMIN_ID", "").strip()
    admin_id: int | None = None
    if admin_raw:
        if not admin_raw.isdigit():
            _stop("ADMIN_ID должен состоять только из цифр (узнать свой ID: команда /id).")
        admin_id = int(admin_raw)

    tz_name = os.getenv("TIMEZONE", "").strip() or "Europe/Moscow"
    try:
        timezone = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        _stop(f"Неизвестный часовой пояс TIMEZONE={tz_name}. Пример: Europe/Moscow.")

    return Config(
        bot_token=token,
        admin_id=admin_id,
        timezone=timezone,
        db_path=BASE_DIR / "barber.db",
    )


config = load_config()
