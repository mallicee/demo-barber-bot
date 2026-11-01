"""Пошаговая запись: услуга → дата → время → имя → телефон → подтверждение.

Каждый обработчик привязан к своему шагу (состоянию FSM). Поэтому старые
кнопки из прошлых сообщений не сработают «не к месту» — их поймает
fallback и вежливо скажет, что кнопка устарела.
"""

from datetime import date

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app import database as db
from app.callbacks import BackCb, ConfirmCb, DateCb, MenuCb, ServiceCb, TimeCb
from app.keyboards import (
    BTN_BACK,
    BTN_MENU,
    after_booking_kb,
    choose_date_kb,
    choose_service_kb,
    choose_time_kb,
    confirm_kb,
    main_menu_kb,
    nav_only_kb,
    phone_kb,
)
from app.shop import SERVICES, SHOP_ADDRESS
from app.states import Booking
from app.utils import (
    booking_card,
    day_long,
    day_short,
    get_available_days,
    get_free_hours,
    normalize_phone,
    notify_admin,
    parse_day,
    remove_reply_keyboard,
    reset_state,
    safe_edit,
    user_link,
    validate_name,
)

router = Router(name="booking")


# ---------- Экраны шагов (используются и при движении вперёд, и «Назад») ----------

async def show_service_step(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Booking.service)
    await safe_edit(cb, "📅 <b>Запись · шаг 1 из 5</b>\n\nВыберите услугу:",
                    choose_service_kb())


async def show_date_step(cb: CallbackQuery, state: FSMContext, note: str = "") -> None:
    await state.set_state(Booking.date)
    days = await get_available_days()
    if not days:
        await safe_edit(cb, "😔 На ближайшую неделю свободного времени нет. "
                            "Позвоните нам — постараемся что-нибудь придумать.",
                        nav_only_kb("service"))
        return
    data = await state.get_data()
    service = SERVICES[data["service_id"]]
    await safe_edit(
        cb,
        f"{note}📅 <b>Запись · шаг 2 из 5</b>\n\nУслуга: {service.name}\nВыберите дату:",
        choose_date_kb(days, [day_short(d) for d in days]),
    )


async def show_time_step(cb: CallbackQuery, state: FSMContext, note: str = "") -> None:
    data = await state.get_data()
    day = date.fromisoformat(data["day"])
    hours = await get_free_hours(day)
    if not hours:
        # Пока пользователь думал, день заняли целиком — возвращаем к датам
        await show_date_step(cb, state, note="⚠️ На этот день свободного времени больше нет.\n\n")
        return
    await state.set_state(Booking.time)
    await safe_edit(
        cb,
        f"{note}📅 <b>Запись · шаг 3 из 5</b>\n\nДата: {day_long(day)}\nВыберите время:",
        choose_time_kb(hours),
    )


async def show_name_step(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Booking.name)
    await safe_edit(cb, "👤 <b>Запись · шаг 4 из 5</b>\n\nКак к вам обращаться? "
                        "Напишите имя в ответном сообщении.", nav_only_kb("time"))


async def send_name_step(message: Message, state: FSMContext) -> None:
    """То же, что show_name_step, но новым сообщением (после «Назад» с шага телефона)."""
    await state.set_state(Booking.name)
    await message.answer("👤 <b>Запись · шаг 4 из 5</b>\n\nКак к вам обращаться? "
                         "Напишите имя в ответном сообщении.", reply_markup=nav_only_kb("time"))


async def send_phone_step(bot: Bot, chat_id: int, state: FSMContext) -> None:
    await state.set_state(Booking.phone)
    await bot.send_message(
        chat_id,
        "📞 <b>Запись · шаг 5 из 5</b>\n\n"
        "Нажмите «📱 Поделиться номером» внизу или введите номер вручную, "
        "например: <code>+7 900 123-45-67</code>",
        reply_markup=phone_kb(),
    )


async def send_summary(message: Message, state: FSMContext) -> None:
    await state.set_state(Booking.confirm)
    data = await state.get_data()
    service = SERVICES[data["service_id"]]
    card = booking_card({
        "service_id": service.id, "service_name": service.name, "price": service.price,
        "date": data["day"], "time": f"{data['hour']:02d}:00",
        "client_name": data["name"], "phone": data["phone"],
    })
    await message.answer(f"📋 <b>Проверьте запись</b>\n\n{card}\n\nВсё верно?",
                         reply_markup=confirm_kb())


async def stale(cb: CallbackQuery, state: FSMContext) -> None:
    """Данные записи потерялись (например, бот перезапускался) — в меню."""
    await reset_state(cb.bot, cb.from_user.id, state)
    await cb.answer("Сессия устарела, начните запись заново", show_alert=True)
    await safe_edit(cb, "Выберите, что вас интересует 👇", main_menu_kb())


# ---------- Старт и выбор услуги, даты, времени ----------

@router.callback_query(MenuCb.filter(F.action == "book"))
async def start_booking(cb: CallbackQuery, state: FSMContext) -> None:
    await reset_state(cb.bot, cb.from_user.id, state)
    await show_service_step(cb, state)
    await cb.answer()


@router.callback_query(Booking.service, ServiceCb.filter())
async def choose_service(cb: CallbackQuery, callback_data: ServiceCb, state: FSMContext) -> None:
    if callback_data.service_id not in SERVICES:
        await cb.answer("Такой услуги нет", show_alert=True)
        return
    await state.update_data(service_id=callback_data.service_id)
    await show_date_step(cb, state)
    await cb.answer()


@router.callback_query(Booking.date, DateCb.filter())
async def choose_date(cb: CallbackQuery, callback_data: DateCb, state: FSMContext) -> None:
    if "service_id" not in await state.get_data():
        await stale(cb, state)
        return
    day = parse_day(callback_data.day)
    if day is None or day not in await get_available_days():
        await cb.answer("Эта дата уже недоступна, выберите другую", show_alert=True)
        await show_date_step(cb, state)
        return
    await state.update_data(day=day.isoformat())
    await show_time_step(cb, state)
    await cb.answer()


@router.callback_query(Booking.time, TimeCb.filter())
async def choose_time(cb: CallbackQuery, callback_data: TimeCb, state: FSMContext) -> None:
    data = await state.get_data()
    if "day" not in data:
        await stale(cb, state)
        return
    if callback_data.hour not in await get_free_hours(date.fromisoformat(data["day"])):
        await cb.answer("Это время уже занято, выберите другое", show_alert=True)
        await show_time_step(cb, state)
        return
    await state.update_data(hour=callback_data.hour)
    await show_name_step(cb, state)
    await cb.answer()


# ---------- Кнопки «Назад» (inline) ----------

@router.callback_query(Booking.date, BackCb.filter(F.to == "service"))
async def back_to_service(cb: CallbackQuery, state: FSMContext) -> None:
    await show_service_step(cb, state)
    await cb.answer()


@router.callback_query(Booking.time, BackCb.filter(F.to == "date"))
async def back_to_date(cb: CallbackQuery, state: FSMContext) -> None:
    if "service_id" not in await state.get_data():
        await stale(cb, state)
        return
    await show_date_step(cb, state)
    await cb.answer()


@router.callback_query(Booking.name, BackCb.filter(F.to == "time"))
async def back_to_time(cb: CallbackQuery, state: FSMContext) -> None:
    if "day" not in await state.get_data():
        await stale(cb, state)
        return
    await show_time_step(cb, state)
    await cb.answer()


@router.callback_query(Booking.confirm, BackCb.filter(F.to == "phone"))
async def back_to_phone(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    if isinstance(cb.message, Message):
        try:
            await cb.message.edit_reply_markup(reply_markup=None)  # убираем кнопки у итога
        except TelegramBadRequest:
            pass
    await send_phone_step(cb.bot, cb.from_user.id, state)


# ---------- Шаг 4: имя ----------

@router.message(Booking.name, F.text)
async def enter_name(message: Message, state: FSMContext) -> None:
    name = validate_name(message.text)
    if name is None:
        await message.answer("Пожалуйста, введите имя буквами (от 2 до 40 символов), "
                             "например: <i>Алексей</i>", reply_markup=nav_only_kb("time"))
        return
    await state.update_data(name=name)
    await send_phone_step(message.bot, message.chat.id, state)


@router.message(Booking.name)
async def enter_name_wrong_type(message: Message) -> None:
    # Стикер, фото, голосовое и т.п. вместо имени
    await message.answer("Напишите, пожалуйста, имя текстом 🙂", reply_markup=nav_only_kb("time"))


# ---------- Шаг 5: телефон ----------

@router.message(Booking.phone, F.text == BTN_BACK)
async def phone_back(message: Message, state: FSMContext) -> None:
    await remove_reply_keyboard(message.bot, message.chat.id)
    await send_name_step(message, state)


@router.message(Booking.phone, F.text == BTN_MENU)
async def phone_menu(message: Message, state: FSMContext) -> None:
    await reset_state(message.bot, message.chat.id, state)
    await message.answer("Запись отменена. Выберите, что вас интересует 👇",
                         reply_markup=main_menu_kb())


async def _accept_phone(message: Message, state: FSMContext, phone: str) -> None:
    await state.update_data(phone=phone)
    await remove_reply_keyboard(message.bot, message.chat.id)
    await send_summary(message, state)


@router.message(Booking.phone, F.contact)
async def phone_contact(message: Message, state: FSMContext) -> None:
    phone = normalize_phone(message.contact.phone_number)
    if phone is None:
        await message.answer("Не получилось прочитать номер, введите его вручную.")
        return
    await _accept_phone(message, state, phone)


@router.message(Booking.phone, F.text)
async def phone_text(message: Message, state: FSMContext) -> None:
    phone = normalize_phone(message.text)
    if phone is None:
        await message.answer("Похоже, номер введён с ошибкой. Пример: "
                             "<code>+7 900 123-45-67</code> или <code>89001234567</code>")
        return
    await _accept_phone(message, state, phone)


@router.message(Booking.phone)
async def phone_wrong_type(message: Message) -> None:
    await message.answer("Отправьте номер текстом или нажмите «📱 Поделиться номером».")


# ---------- Подтверждение ----------

@router.callback_query(Booking.confirm, ConfirmCb.filter(F.ok == False))  # noqa: E712
async def confirm_cancel(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await safe_edit(cb, "Запись отменена. Выберите, что вас интересует 👇", main_menu_kb())
    await cb.answer()


@router.callback_query(Booking.confirm, ConfirmCb.filter(F.ok == True))  # noqa: E712
async def confirm_booking(cb: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    if not {"service_id", "day", "hour", "name", "phone"} <= data.keys():
        await stale(cb, state)
        return
    # Сразу выходим из шага подтверждения: защита от двойного нажатия
    await state.set_state(None)

    service = SERVICES[data["service_id"]]
    day = date.fromisoformat(data["day"])
    booking_id = None
    if data["hour"] in await get_free_hours(day):
        booking_id = await db.add_booking(
            user_id=cb.from_user.id,
            username=cb.from_user.username,
            client_name=data["name"],
            phone=data["phone"],
            service_id=service.id,
            service_name=service.name,
            price=service.price,
            date=data["day"],
            time=f"{data['hour']:02d}:00",
        )
    if booking_id is None:
        # Время успело занять кто-то другой (или оно уже прошло)
        await cb.answer("Это время только что заняли 😔", show_alert=True)
        await show_time_step(cb, state, note="⚠️ Выбранное время уже недоступно.\n\n")
        return

    await state.clear()
    booking = await db.get_booking(booking_id)
    await safe_edit(
        cb,
        f"✅ <b>Вы записаны!</b> Номер записи: #{booking_id}\n\n{booking_card(booking)}\n\n"
        f"Ждём вас по адресу: {SHOP_ADDRESS}",
        after_booking_kb(),
    )
    await cb.answer("Готово!")
    await notify_admin(
        cb.bot,
        f"🆕 <b>Новая запись #{booking_id}</b>\n\n{booking_card(booking)}\n"
        f"💬 Telegram: {user_link(cb.from_user.id, cb.from_user.username)}",
    )
