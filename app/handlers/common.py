"""Общие команды и информационные экраны: /start, /id, услуги, контакты, о нас."""

from html import escape

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.callbacks import MenuCb
from app.keyboards import back_to_menu_kb, main_menu_kb, services_info_kb
from app.shop import ABOUT_TEXT, CONTACTS_TEXT, SERVICES, SHOP_NAME
from app.utils import reset_state, safe_edit

router = Router(name="common")

MENU_TEXT = "Выберите, что вас интересует 👇"


def services_text() -> str:
    lines = ["💈 <b>Услуги и цены</b>\n"]
    for s in SERVICES.values():
        lines.append(f"• <b>{s.name}</b> — {s.price} ₽, {s.duration} мин")
    lines.append("\nЗапишитесь онлайн — это займёт меньше минуты.")
    return "\n".join(lines)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await reset_state(message.bot, message.chat.id, state)
    name = escape(message.from_user.first_name or "гость")
    await message.answer(
        f"Привет, {name}! 👋\n\n"
        f"Это бот барбершопа «<b>{SHOP_NAME}</b>». Здесь можно посмотреть цены "
        "и записаться на стрижку в пару касаний.\n\n" + MENU_TEXT,
        reply_markup=main_menu_kb(),
    )


@router.message(Command("id"))
async def cmd_id(message: Message) -> None:
    # Состояние не трогаем: /id можно вызвать в любой момент
    await message.answer(
        f"Ваш Telegram ID: <code>{message.from_user.id}</code>\n\n"
        "Нажмите на число, чтобы скопировать, и вставьте в .env как ADMIN_ID."
    )


@router.message(Command("admin"))
async def cmd_admin_denied(message: Message) -> None:
    # Сюда попадают только не-админы: админа перехватывает роутер admin
    await message.answer("Эта команда доступна только владельцу барбершопа.")


@router.callback_query(MenuCb.filter(F.action == "main"))
async def show_main_menu(cb: CallbackQuery, state: FSMContext) -> None:
    await reset_state(cb.bot, cb.from_user.id, state)
    await safe_edit(cb, f"🏠 <b>{SHOP_NAME}</b>\n\n{MENU_TEXT}", main_menu_kb())
    await cb.answer()


@router.callback_query(MenuCb.filter(F.action == "services"))
async def show_services(cb: CallbackQuery, state: FSMContext) -> None:
    await reset_state(cb.bot, cb.from_user.id, state)
    await safe_edit(cb, services_text(), services_info_kb())
    await cb.answer()


@router.callback_query(MenuCb.filter(F.action == "contacts"))
async def show_contacts(cb: CallbackQuery, state: FSMContext) -> None:
    await reset_state(cb.bot, cb.from_user.id, state)
    await safe_edit(cb, CONTACTS_TEXT, back_to_menu_kb())
    await cb.answer()


@router.callback_query(MenuCb.filter(F.action == "about"))
async def show_about(cb: CallbackQuery, state: FSMContext) -> None:
    await reset_state(cb.bot, cb.from_user.id, state)
    await safe_edit(cb, ABOUT_TEXT, back_to_menu_kb())
    await cb.answer()
