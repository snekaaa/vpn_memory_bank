"""
Хэндлер команды /start с упрощенным меню (4 кнопки)
"""

from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from keyboards.main_menu import get_main_menu_keyboard, get_main_menu, get_user_subscription_days
from templates.messages import (
    get_download_apps_message,
    get_vpn_key_message,
    get_no_key_error
)
from services.vpn_manager_x3ui import vpn_manager_x3ui as vpn_manager
import structlog
import os

logger = structlog.get_logger(__name__)

start_router = Router()

# Admin Telegram IDs для security check
ADMIN_TELEGRAM_IDS = [int(x) for x in os.getenv('ADMIN_TELEGRAM_IDS', '').split(',') if x.strip()]

def _is_admin_user(user_id: int) -> bool:
    return user_id in ADMIN_TELEGRAM_IDS

@start_router.message(Command("start"))
async def start_command(message: types.Message, state: FSMContext):
    """Обработка команды /start: показывает главное меню с подписками"""
    try:
        telegram_id = message.from_user.id
        user_data = {
            "username": message.from_user.username,
            "first_name": message.from_user.first_name,
            "last_name": message.from_user.last_name,
            "language_code": message.from_user.language_code
        }
        is_admin = _is_admin_user(telegram_id)
        logger.info("Authorization starting", telegram_id=telegram_id, username=user_data.get("username"), is_admin=is_admin)
        
        first_name = message.from_user.first_name if message.from_user.first_name else "друг"
        welcome_msg = (
            f"👋 *{first_name}, добро пожаловать!*\n\n"
            f"🔓 Получите свободный доступ к интернету\n"
            f"💳 Выберите подписку для получения VPN ключей\n"
            f"🔑 Управляйте своими ключами\n\n"
            f"Выберите действие в меню ниже:"
        )
        
        # Получаем количество дней до окончания подписки
        days_remaining = await get_user_subscription_days(telegram_id)
        
        await message.answer(
            welcome_msg,
            reply_markup=get_main_menu(days_remaining),
            parse_mode="Markdown"
        )
        
        logger.info("Authorization successful", telegram_id=telegram_id, is_admin=is_admin)
        
    except Exception as e:
        logger.error("Authorization error", error=str(e))
        
        # Получаем количество дней даже при ошибке
        try:
            days_remaining = await get_user_subscription_days(telegram_id)
        except:
            days_remaining = 0
            
        await message.answer(
            "⚠️ Произошла ошибка при запуске\nПопробуйте еще раз /start",
            reply_markup=get_main_menu(days_remaining)
        )

@start_router.message(F.text == "🔑 Мой VPN ключ")
async def vpn_key_handler(message: types.Message):
    """Обработчик кнопки 'Мой VPN ключ' - сразу показывает ключ"""
    try:
        telegram_id = message.from_user.id
        username = message.from_user.username or ""
        first_name = message.from_user.first_name or ""
        
        logger.info("User requested VPN key", telegram_id=telegram_id, username=username, first_name=first_name)
        
        # Показываем индикатор загрузки
        loading_msg = await message.answer(
            "🔄 Получаем ваш VPN ключ...",
        )
        
        try:
            # Получаем или создаем ключ через VPN менеджер
            vpn_key_data = await vpn_manager.get_or_create_user_key(telegram_id, username, first_name)
            
            if vpn_key_data and vpn_key_data.get('vless_url'):
                # Отправляем сообщение с ключом
                message_text = get_vpn_key_message(vpn_key_data['vless_url'], is_update=False)
                
                await loading_msg.edit_text(
                    message_text,
                    parse_mode="Markdown",
                    reply_markup=get_main_menu_keyboard()
                )
                
                logger.info("VPN key provided to user", 
                           telegram_id=telegram_id,
                           key_id=vpn_key_data.get('id'))
            else:
                # Ошибка получения ключа
                await loading_msg.edit_text(
                    get_no_key_error(),
                    reply_markup=get_main_menu_keyboard()
                )
                
                logger.error("Failed to provide VPN key", telegram_id=telegram_id)
                
        except Exception as e:
            logger.error("Error getting VPN key", 
                        telegram_id=telegram_id, 
                        error=str(e))
            
            await loading_msg.edit_text(
                get_no_key_error(),
                reply_markup=get_main_menu_keyboard()
            )
            
    except Exception as e:
        logger.error("Error handling VPN key request", error=str(e))
        await message.answer("❌ Произошла ошибка")

@start_router.message(F.text == "📱 Приложения")
async def apps_handler(message: types.Message):
    """Обработчик кнопки Приложения"""
    try:
        await message.answer(
            get_download_apps_message(),
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.error("Error handling apps", error=str(e))
        await message.answer("❌ Произошла ошибка")

@start_router.message(F.text == "🧑🏼‍💻 Служба поддержки")
async def support_handler(message: types.Message):
    """Обработчик кнопки Служба поддержки"""
    try:
        support_keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(
                text="💬 Написать в поддержку",
                url="https://t.me/bez_lagov"
            )]
        ])
        
        await message.answer(
            "🧑🏼‍💻 *Служба поддержки*\n\n"
            "Свяжитесь с нами напрямую:",
            reply_markup=support_keyboard,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error("Error handling support", error=str(e))
        await message.answer("❌ Произошла ошибка") 