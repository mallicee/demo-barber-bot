"""«Ловушка» для всего, что не обработали другие роутеры.

Подключается последней. Благодаря ей бот спокойно реагирует на
случайный текст, стикеры, фото и нажатия устаревших кнопок.
"""

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.states import Booking

router = Router(name="fallback")

# Шаги, где нужно нажимать кнопки, а не писать текст
BUTTON_STEPS = {Booking.service.state, Booking.date.state,
                Booking.time.state, Booking.confirm.state}


@router.message()
async def unknown_message(message: Message, state: FSMContext) -> None:
    if await state.get_state() in BUTTON_STEPS:
        await message.answer("Пожалуйста, выберите вариант кнопками выше 👆\n"
                             "Начать заново: /start")
    else:
        await message.answer("Я понимаю кнопки и команды 🙂\n"
                             "Нажмите /start, чтобы открыть меню.")


@router.callback_query()
async def unknown_callback(cb: CallbackQuery) -> None:
    await cb.answer("Эта кнопка устарела. Откройте меню командой /start",
                    show_alert=True)
