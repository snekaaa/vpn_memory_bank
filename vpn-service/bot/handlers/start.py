"""
Хэндлер команды /start с упрощенным меню (4 кнопки)
"""

from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from keyboards.main_menu import get_main_menu_keyboard, get_main_menu, get_user_subscription_days, send_main_menu
from templates.messages import (
    get_download_apps_message,
    get_vpn_key_message,
    get_no_key_error
)
from services.vpn_manager_x3ui import vpn_manager_x3ui as vpn_manager
import structlog
import os
import asyncio

logger = structlog.get_logger(__name__)

start_router = Router()

async def _is_admin_user(user_id: int) -> bool:
    """Проверка является ли пользователь админом через настройки из БД"""
    try:
        # Импортируем здесь, чтобы избежать циклических импортов
        import sys
        import os
        
        # Добавляем backend в path
        backend_path = os.path.join(os.path.dirname(__file__), '..', 'backend')
        if backend_path not in sys.path:
            sys.path.insert(0, backend_path)
        
        from config.database import get_db_session
        from services.app_settings_service import AppSettingsService
        
        async with get_db_session() as session:
            is_admin = await AppSettingsService.is_admin_telegram_id(session, user_id)
            return is_admin
    except Exception as e:
        logger.error("Error checking admin status", user_id=user_id, error=str(e))
        # Fallback к ENV переменной
        admin_ids = [int(x) for x in os.getenv('ADMIN_TELEGRAM_IDS', '').split(',') if x.strip()]
        return user_id in admin_ids

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
        
        # Быстрая проверка админского статуса через ENV (без БД)
        admin_ids = [int(x) for x in os.getenv('ADMIN_TELEGRAM_IDS', '').split(',') if x.strip()]
        is_admin = telegram_id in admin_ids
        
        logger.info("Authorization starting", telegram_id=telegram_id, username=user_data.get("username"), is_admin=is_admin)
        
        first_name = message.from_user.first_name if message.from_user.first_name else "друг"
        
        # Простое приветственное сообщение без обращения к БД
        welcome_msg = (
            f"👋 *{first_name}, добро пожаловать!*\n\n"
            f"🔓 Получите свободный доступ к интернету\n"
            f"💳 Выберите подписку для получения VPN ключей\n"
            f"🔑 Управляйте своими ключами\n\n"
            f"Выберите действие в меню ниже:"
        )
        
        # Сначала отправляем ответ пользователю (быстро)
        await send_main_menu(message, telegram_id, welcome_msg)
        logger.info("Authorization successful", telegram_id=telegram_id, is_admin=is_admin)
        
        # Затем асинхронно проверяем админский статус из БД (медленно, но не блокирует)
        asyncio.create_task(_check_admin_status_async(telegram_id, is_admin))
        
    except Exception as e:
        logger.error("Authorization error", error=str(e))
        try:
            await send_main_menu(message, message.from_user.id, "⚠️ Произошла ошибка при запуске\nПопробуйте еще раз /start")
        except:
            await message.answer("⚠️ Произошла ошибка при запуске\nПопробуйте еще раз /start")

async def _check_admin_status_async(telegram_id: int, current_is_admin: bool):
    """Асинхронная проверка админского статуса из БД (не блокирует основной поток)"""
    try:
        # Импортируем здесь, чтобы избежать циклических импортов
        import sys
        import os
        
        # Добавляем backend в path
        backend_path = os.path.join(os.path.dirname(__file__), '..', 'backend')
        if backend_path not in sys.path:
            sys.path.insert(0, backend_path)
        
        from config.database import get_db_session
        from services.app_settings_service import AppSettingsService
        
        async with get_db_session() as session:
            db_is_admin = await AppSettingsService.is_admin_telegram_id(session, telegram_id)
            
            if db_is_admin != current_is_admin:
                logger.info("Admin status mismatch detected", 
                           telegram_id=telegram_id, 
                           env_is_admin=current_is_admin, 
                           db_is_admin=db_is_admin)
                
    except Exception as e:
        logger.error("Error in async admin status check", 
                    telegram_id=telegram_id, 
                    error=str(e))
        # Не критично - пользователь уже получил ответ

@start_router.message(F.text == "🔐 Получить VPN доступ")
async def get_vpn_access_handler(message: types.Message):
    """Обработчик кнопки 'Получить VPN доступ' - показывает планы подписки с toggle автоплатежа"""
    try:
        telegram_id = message.from_user.id
        logger.info("User requested VPN access (no subscription)", telegram_id=telegram_id)
        
        # Получаем настройки автоплатежа пользователя
        try:
            # Импортируем SimpleAPIClient для получения настроек
            from handlers.payments import SimpleAPIClient
            api_client = SimpleAPIClient()
            auto_payment_info = await api_client.get_user_auto_payment_info(telegram_id)
            autopay_enabled = auto_payment_info.get('enabled', True)  # Default to True if not found
        except Exception as e:
            logger.error(f"Error getting autopay settings: {e}")
            autopay_enabled = True  # Fallback to default
        
        # Показываем планы подписки с toggle автоплатежа
        from keyboards.main_menu import get_subscription_keyboard_with_autopay_toggle
        
        subscription_keyboard = await get_subscription_keyboard_with_autopay_toggle(autopay_enabled)
        
        await message.answer(
            "💳 **Выберите план подписки:**\n\n"
            "📊 Доступные тарифы для подключения VPN сервиса",
            reply_markup=subscription_keyboard,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error("Error in get_vpn_access_handler", error=str(e))
        await message.answer("⚠️ Произошла ошибка. Попробуйте позже.")

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
                # Используем расширенное сообщение с информацией о сервере
                try:
                    from handlers.vpn_simplified import enhance_vpn_key_message
                    message_text, keyboard = await enhance_vpn_key_message(
                        vpn_key_data['vless_url'], 
                        telegram_id, 
                        is_update=False
                    )
                except Exception as e:
                    # Fallback к базовому шаблону с сервером
                    from templates.messages import get_vpn_key_message_with_server
                    from handlers.vpn_simplified import DEMO_COUNTRIES
                    default_country = DEMO_COUNTRIES[0]  # Нидерланды
                    message_text = get_vpn_key_message_with_server(
                        vpn_key_data['vless_url'], 
                        default_country, 
                        is_update=False
                    )
                    keyboard = get_main_menu_keyboard()
                
                await loading_msg.edit_text(
                    message_text,
                    parse_mode="Markdown",
                    reply_markup=keyboard
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