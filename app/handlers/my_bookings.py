"""«Мои записи»: список будущих записей клиента и их отмена."""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from app import database as db
from app.callbacks import MenuCb, MyCancelCb
from app.keyboards import my_bookings_kb, my_cancel_confirm_kb
from app.utils import (
    booking_card,
    booking_label,
    is_future,
    notify_admin,
    now,
    reset_state,
    safe_edit,
    user_link,
)

router = Router(name="my_bookings")


async def show_my_bookings(cb: CallbackQuery, note: str = "") -> None:
    current = now()
    bookings = await db.get_upcoming(
        current.date().isoformat(), current.strftime("%H:%M"), user_id=cb.from_user.id
    )
    if not bookings:
        text = f"{note}🗂 У вас пока нет предстоящих записей."
    else:
        blocks = [f"<b>#{b['id']}</b>\n{booking_card(b)}" for b in bookings]
        text = f"{note}🗂 <b>Ваши записи</b>\n\n" + "\n\n".join(blocks)
    labels = [booking_label(b) for b in bookings]
    await safe_edit(cb, text, my_bookings_kb(bookings, labels))


@router.callback_query(MenuCb.filter(F.action == "my"))
async def my_bookings(cb: CallbackQuery, state: FSMContext) -> None:
    await reset_state(cb.bot, cb.from_user.id, state)
    await show_my_bookings(cb)
    await cb.answer()


@router.callback_query(MyCancelCb.filter(F.sure == False))  # noqa: E712
async def ask_cancel(cb: CallbackQuery, callback_data: MyCancelCb) -> None:
    booking = await db.get_booking(callback_data.booking_id)
    # Проверяем, что запись своя, активна и ещё не прошла
    if (not booking or booking["user_id"] != cb.from_user.id
            or booking["status"] != "active" or not is_future(booking)):
        await cb.answer("Эта запись уже неактуальна", show_alert=True)
        await show_my_bookings(cb)
        return
    await safe_edit(cb, f"Отменить запись?\n\n{booking_card(booking)}",
                    my_cancel_confirm_kb(booking["id"]))
    await cb.answer()


@router.callback_query(MyCancelCb.filter(F.sure == True))  # noqa: E712
async def do_cancel(cb: CallbackQuery, callback_data: MyCancelCb) -> None:
    booking = await db.get_booking(callback_data.booking_id)
    ok = (booking is not None and is_future(booking)
          and await db.cancel_booking(callback_data.booking_id, user_id=cb.from_user.id))
    if not ok:
        # Повторное нажатие или запись уже отменена/прошла
        await cb.answer("Запись уже отменена или неактуальна", show_alert=True)
        await show_my_bookings(cb)
        return
    await cb.answer("Запись отменена")
    await show_my_bookings(cb, note="✅ Запись отменена.\n\n")
    await notify_admin(
        cb.bot,
        f"❌ <b>Клиент отменил запись #{booking['id']}</b>\n\n{booking_card(booking)}\n"
        f"💬 Telegram: {user_link(cb.from_user.id, cb.from_user.username)}",
    )
