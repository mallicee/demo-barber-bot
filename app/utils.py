"""Вспомогательные функции: время, форматирование, безопасная отправка."""

import logging
import re
from datetime import date, datetime, time, timedelta
from html import escape

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from app import database as db
from app.config import config
from app.shop import DAYS_AHEAD, SERVICES, WORK_END_HOUR, WORK_START_HOUR
from app.states import Booking

log = logging.getLogger(__name__)

WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля",
          "августа", "сентября", "октября", "ноября", "декабря"]


# ---------- Время и слоты ----------

def now() -> datetime:
    """Текущее время в часовом поясе барбершопа (без tzinfo для простоты)."""
    return datetime.now(config.timezone).replace(tzinfo=None)


async def get_free_hours(day: date) -> list[int]:
    """Свободные часы на день: без занятых и уже прошедших слотов."""
    busy = await db.get_busy_times(day.isoformat())
    current = now()
    return [
        hour for hour in range(WORK_START_HOUR, WORK_END_HOUR)
        if datetime.combine(day, time(hour)) > current and f"{hour:02d}:00" not in busy
    ]


async def get_available_days() -> list[date]:
    """Ближайшие DAYS_AHEAD дней, в которых осталось хоть одно свободное время."""
    today = now().date()
    days = [today + timedelta(days=i) for i in range(DAYS_AHEAD)]
    return [d for d in days if await get_free_hours(d)]


def parse_day(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def is_future(booking: dict) -> bool:
    start = datetime.fromisoformat(f"{booking['date']}T{booking['time']}")
    return start > now()


# ---------- Форматирование ----------

def day_short(d: date) -> str:
    """'Пн 03.11' — для кнопок."""
    today = now().date()
    if d == today:
        prefix = "Сегодня"
    elif d == today + timedelta(days=1):
        prefix = "Завтра"
    else:
        prefix = WEEKDAYS[d.weekday()]
    return f"{prefix} {d:%d.%m}"


def day_long(d: date) -> str:
    """'3 ноября (пн)' — для текста."""
    return f"{d.day} {MONTHS[d.month - 1]} ({WEEKDAYS[d.weekday()].lower()})"


def booking_label(b: dict) -> str:
    """Короткая подпись записи для кнопки: '03.11 14:00'."""
    d = date.fromisoformat(b["date"])
    return f"{d:%d.%m} {b['time']}"


def booking_card(b: dict) -> str:
    """Полное описание записи (HTML). Пользовательский ввод экранируется."""
    service = SERVICES.get(b["service_id"])
    duration = f" ({service.duration} мин)" if service else ""
    d = date.fromisoformat(b["date"])
    return (
        f"💈 Услуга: {escape(b['service_name'])}{duration}\n"
        f"💰 Стоимость: {b['price']} ₽\n"
        f"📅 Дата: {day_long(d)}\n"
        f"🕐 Время: {b['time']}\n"
        f"👤 Имя: {escape(b['client_name'])}\n"
        f"📞 Телефон: {escape(b['phone'])}"
    )


def user_link(user_id: int, username: str | None) -> str:
    link = f'<a href="tg://user?id={user_id}">профиль</a>'
    return f"@{escape(username)} ({link})" if username else link


# ---------- Проверка ввода ----------

def normalize_phone(raw: str) -> str | None:
    """Приводит телефон к виду +79001234567. None — если формат неверный."""
    cleaned = re.sub(r"[\s\-()]", "", raw or "")
    if not re.fullmatch(r"\+?\d{10,15}", cleaned):
        return None
    if cleaned.startswith("8") and len(cleaned) == 11:
        return "+7" + cleaned[1:]              # 89001234567 -> +79001234567
    if not cleaned.startswith("+"):
        if len(cleaned) == 10:
            return "+7" + cleaned              # 9001234567 -> +79001234567
        return "+" + cleaned
    return cleaned


def validate_name(raw: str) -> str | None:
    """Имя: 2–40 символов, только буквы, пробел, дефис, апостроф, точка."""
    name = " ".join((raw or "").split())
    if not 2 <= len(name) <= 40:
        return None
    if not all(ch.isalpha() or ch in " -'." for ch in name):
        return None
    if not any(ch.isalpha() for ch in name):
        return None
    return name


# ---------- Отправка сообщений ----------

async def safe_edit(cb: CallbackQuery, text: str, reply_markup=None) -> None:
    """Редактирует сообщение с кнопкой. Если нельзя (сообщение старое,
    удалено или это не текст) — отправляет новое. Ошибка «сообщение
    не изменилось» при повторном нажатии просто игнорируется."""
    if isinstance(cb.message, Message):
        try:
            await cb.message.edit_text(text, reply_markup=reply_markup)
            return
        except TelegramBadRequest as e:
            if "message is not modified" in str(e):
                return
    await cb.bot.send_message(cb.from_user.id, text, reply_markup=reply_markup)


async def send_long(bot: Bot, chat_id: int, text: str, reply_markup=None) -> None:
    """Отправляет длинный текст частями (лимит Telegram — 4096 символов)."""
    parts, current = [], ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > 3900:
            parts.append(current)
            current = ""
        current += line + "\n"
    parts.append(current)
    for i, part in enumerate(parts):
        is_last = i == len(parts) - 1
        await bot.send_message(chat_id, part, reply_markup=reply_markup if is_last else None)


async def notify_admin(bot: Bot, text: str) -> None:
    """Уведомление владельцу. Ошибки не роняют бота (например, если
    админ ещё ни разу не писал боту или ADMIN_ID не указан)."""
    if not config.admin_id:
        log.warning("ADMIN_ID не указан в .env — уведомление не отправлено")
        return
    try:
        await bot.send_message(config.admin_id, text)
    except TelegramAPIError as e:
        log.warning("Не удалось отправить уведомление админу: %s", e)


async def remove_reply_keyboard(bot: Bot, chat_id: int) -> None:
    """Убирает обычную клавиатуру (с кнопкой «Поделиться номером»)."""
    try:
        msg = await bot.send_message(chat_id, "⌛", reply_markup=ReplyKeyboardRemove())
        await bot.delete_message(chat_id, msg.message_id)
    except TelegramAPIError:
        pass


async def reset_state(bot: Bot, chat_id: int, state: FSMContext) -> None:
    """Сбрасывает запись. Если пользователь был на шаге телефона —
    заодно прячет клавиатуру с номером."""
    if await state.get_state() == Booking.phone.state:
        await remove_reply_keyboard(bot, chat_id)
    await state.clear()
