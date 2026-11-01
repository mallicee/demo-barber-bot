"""Панель владельца (/admin). Доступна только пользователю с ADMIN_ID."""

from datetime import date, timedelta
from html import escape

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app import database as db
from app.callbacks import AdminCancelCb, AdminCb
from app.config import config
from app.keyboards import (
    admin_back_kb,
    admin_cancel_confirm_kb,
    admin_cancel_list_kb,
    admin_menu_kb,
)
from app.shop import SHOP_PHONE
from app.utils import (
    booking_card,
    booking_label,
    day_long,
    is_future,
    now,
    reset_state,
    safe_edit,
    send_long,
)

router = Router(name="admin")
# Все обработчики этого роутера срабатывают только для админа.
# Если ADMIN_ID не указан, условие никогда не выполнится.
router.message.filter(F.from_user.id == config.admin_id)
router.callback_query.filter(F.from_user.id == config.admin_id)

ADMIN_TITLE = "🔐 <b>Панель владельца</b>\n\nВыберите действие:"


def bookings_report(title: str, bookings: list[dict]) -> str:
    """Текст отчёта, сгруппированный по дням."""
    if not bookings:
        return f"{title}\n\nЗаписей нет."
    lines = [title]
    current_day = None
    for b in bookings:
        if b["date"] != current_day:
            current_day = b["date"]
            lines.append(f"\n📅 <b>{day_long(date.fromisoformat(current_day))}</b>")
        lines.append(f"{b['time']} — {escape(b['client_name'])}, {escape(b['phone'])}, "
                     f"{escape(b['service_name'])} ({b['price']} ₽) · #{b['id']}")
    lines.append(f"\nВсего: {len(bookings)}")
    return "\n".join(lines)


async def show_report(cb: CallbackQuery, text: str) -> None:
    if len(text) <= 3900:
        await safe_edit(cb, text, admin_back_kb())
    else:
        await send_long(cb.bot, cb.from_user.id, text, admin_back_kb())


async def show_cancel_list(cb: CallbackQuery, note: str = "") -> None:
    current = now()
    bookings = await db.get_upcoming(current.date().isoformat(), current.strftime("%H:%M"),
                                     limit=30)
    if not bookings:
        await safe_edit(cb, f"{note}Будущих записей нет.", admin_back_kb())
        return
    labels = [f"{booking_label(b)} · {b['client_name'][:20]} · #{b['id']}" for b in bookings]
    await safe_edit(cb, f"{note}Выберите запись для отмены (ближайшие 30):",
                    admin_cancel_list_kb(bookings, labels))


@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext) -> None:
    await reset_state(message.bot, message.chat.id, state)
    await message.answer(ADMIN_TITLE, reply_markup=admin_menu_kb())


@router.callback_query(AdminCb.filter(F.action == "menu"))
async def admin_menu(cb: CallbackQuery) -> None:
    await safe_edit(cb, ADMIN_TITLE, admin_menu_kb())
    await cb.answer()


@router.callback_query(AdminCb.filter(F.action == "today"))
async def admin_today(cb: CallbackQuery) -> None:
    today = now().date()
    bookings = await db.get_bookings_between(today.isoformat(), today.isoformat())
    await show_report(cb, bookings_report(f"📋 <b>Записи на сегодня, {day_long(today)}</b>",
                                          bookings))
    await cb.answer()


@router.callback_query(AdminCb.filter(F.action == "week"))
async def admin_week(cb: CallbackQuery) -> None:
    today = now().date()
    end = today + timedelta(days=6)
    bookings = await db.get_bookings_between(today.isoformat(), end.isoformat())
    await show_report(cb, bookings_report(
        f"🗓 <b>Записи на неделю ({today:%d.%m} – {end:%d.%m})</b>", bookings))
    await cb.answer()


@router.callback_query(AdminCb.filter(F.action == "cancel"))
async def admin_cancel_list(cb: CallbackQuery) -> None:
    await show_cancel_list(cb)
    await cb.answer()


@router.callback_query(AdminCancelCb.filter(F.sure == False))  # noqa: E712
async def admin_cancel_ask(cb: CallbackQuery, callback_data: AdminCancelCb) -> None:
    booking = await db.get_booking(callback_data.booking_id)
    if not booking or booking["status"] != "active" or not is_future(booking):
        await cb.answer("Запись уже отменена или прошла", show_alert=True)
        await show_cancel_list(cb)
        return
    await safe_edit(cb, f"Отменить запись #{booking['id']}?\n\n{booking_card(booking)}\n\n"
                        "Клиент получит уведомление.",
                    admin_cancel_confirm_kb(booking["id"]))
    await cb.answer()


@router.callback_query(AdminCancelCb.filter(F.sure == True))  # noqa: E712
async def admin_cancel_do(cb: CallbackQuery, callback_data: AdminCancelCb) -> None:
    booking = await db.get_booking(callback_data.booking_id)
    if not booking or not await db.cancel_booking(callback_data.booking_id):
        await cb.answer("Запись уже отменена", show_alert=True)
        await show_cancel_list(cb)
        return
    await cb.answer("Запись отменена")

    # Сообщаем клиенту
    client_notified = True
    try:
        await cb.bot.send_message(
            booking["user_id"],
            f"😔 <b>Ваша запись #{booking['id']} отменена барбершопом.</b>\n\n"
            f"{booking_card(booking)}\n\n"
            f"Приносим извинения! Записаться заново можно через /start "
            f"или по телефону {SHOP_PHONE}.",
        )
    except TelegramAPIError:
        client_notified = False  # клиент заблокировал бота

    note = "✅ Запись отменена" + ("" if client_notified else
                                   " (клиенту не удалось отправить уведомление)") + ".\n\n"
    await show_cancel_list(cb, note=note)
