"""Все клавиатуры бота."""

from datetime import date

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from app.callbacks import (
    AdminCancelCb,
    AdminCb,
    BackCb,
    ConfirmCb,
    DateCb,
    MenuCb,
    MyCancelCb,
    ServiceCb,
    TimeCb,
)
from app.shop import SERVICES

# Тексты обычных (reply) кнопок на шаге ввода телефона
BTN_SHARE_PHONE = "📱 Поделиться номером"
BTN_BACK = "⬅️ Назад"
BTN_MENU = "🏠 В меню"


def _btn(text: str, cb) -> InlineKeyboardButton:
    """Короткий помощник: inline-кнопка с callback_data."""
    return InlineKeyboardButton(text=text, callback_data=cb.pack())


def _chunks(items: list, size: int) -> list[list]:
    """Разбивает список кнопок на ряды по size штук."""
    return [items[i:i + size] for i in range(0, len(items), size)]


def menu_button() -> InlineKeyboardButton:
    return _btn(BTN_MENU, MenuCb(action="main"))


def nav_row(back_to: str) -> list[InlineKeyboardButton]:
    """Ряд «Назад» + «В меню» для шагов записи."""
    return [_btn(BTN_BACK, BackCb(to=back_to)), menu_button()]


# ---------- Клиент ----------

def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("💈 Услуги и цены", MenuCb(action="services"))],
        [_btn("📅 Записаться", MenuCb(action="book"))],
        [_btn("🗂 Мои записи", MenuCb(action="my"))],
        [_btn("📍 Контакты", MenuCb(action="contacts")),
         _btn("ℹ️ О нас", MenuCb(action="about"))],
    ])


def back_to_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[menu_button()]])


def services_info_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("📅 Записаться", MenuCb(action="book"))],
        [_btn(BTN_BACK, MenuCb(action="main")), menu_button()],
    ])


def choose_service_kb() -> InlineKeyboardMarkup:
    rows = [[_btn(f"{s.name} — {s.price} ₽", ServiceCb(service_id=s.id))]
            for s in SERVICES.values()]
    # С первого шага «Назад» ведёт в главное меню
    rows.append([_btn(BTN_BACK, MenuCb(action="main")), menu_button()])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def choose_date_kb(days: list[date], labels: list[str]) -> InlineKeyboardMarkup:
    buttons = [_btn(label, DateCb(day=d.isoformat())) for d, label in zip(days, labels)]
    rows = _chunks(buttons, 2)
    rows.append(nav_row("service"))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def choose_time_kb(hours: list[int]) -> InlineKeyboardMarkup:
    buttons = [_btn(f"{h:02d}:00", TimeCb(hour=h)) for h in hours]
    rows = _chunks(buttons, 3)
    rows.append(nav_row("date"))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def nav_only_kb(back_to: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[nav_row(back_to)])


def phone_kb() -> ReplyKeyboardMarkup:
    """Обычная клавиатура: только она умеет запрашивать номер телефона."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_SHARE_PHONE, request_contact=True)],
            [KeyboardButton(text=BTN_BACK), KeyboardButton(text=BTN_MENU)],
        ],
        resize_keyboard=True,
        input_field_placeholder="+7 900 123-45-67",
    )


def confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("✅ Подтвердить", ConfirmCb(ok=True)),
         _btn("❌ Отмена", ConfirmCb(ok=False))],
        nav_row("phone"),
    ])


def after_booking_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("🗂 Мои записи", MenuCb(action="my"))],
        [menu_button()],
    ])


def my_bookings_kb(bookings: list[dict], labels: list[str]) -> InlineKeyboardMarkup:
    rows = [[_btn(f"❌ Отменить {label}", MyCancelCb(booking_id=b["id"], sure=False))]
            for b, label in zip(bookings, labels)]
    if not bookings:
        rows.append([_btn("📅 Записаться", MenuCb(action="book"))])
    rows.append([menu_button()])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def my_cancel_confirm_kb(booking_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("Да, отменить", MyCancelCb(booking_id=booking_id, sure=True))],
        [_btn(BTN_BACK, MenuCb(action="my")), menu_button()],
    ])


# ---------- Администратор ----------

def admin_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("📋 Записи на сегодня", AdminCb(action="today"))],
        [_btn("🗓 Записи на неделю", AdminCb(action="week"))],
        [_btn("❌ Отменить запись", AdminCb(action="cancel"))],
    ])


def admin_back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn(BTN_BACK, AdminCb(action="menu"))],
    ])


def admin_cancel_list_kb(bookings: list[dict], labels: list[str]) -> InlineKeyboardMarkup:
    rows = [[_btn(label, AdminCancelCb(booking_id=b["id"], sure=False))]
            for b, label in zip(bookings, labels)]
    rows.append([_btn(BTN_BACK, AdminCb(action="menu"))])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_cancel_confirm_kb(booking_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("Да, отменить запись", AdminCancelCb(booking_id=booking_id, sure=True))],
        [_btn(BTN_BACK, AdminCb(action="cancel"))],
    ])
