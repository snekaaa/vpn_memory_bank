"""
Обработчики команд для нативного меню Telegram
"""

import structlog
from aiogram import Router, types
from aiogram.filters import Command

from services.vpn_manager_x3ui import vpn_manager_x3ui as vpn_manager
from templates.messages import (
    get_vpn_key_message,
    get_download_apps_message, 
    get_support_message,
    get_no_key_error,
    get_key_update_error
)
from keyboards.main_menu import get_main_menu_keyboard

logger = structlog.get_logger(__name__)

# Создаем роутер для команд
commands_router = Router()

@commands_router.message(Command("create_key"))
async def cmd_create_key(message: types.Message):
    """Команда /create_key - создать/напомнить ключ"""
    telegram_id = message.from_user.id
    username = message.from_user.username or ""
    first_name = message.from_user.first_name or ""
    
    logger.info("Command /create_key called", user_id=telegram_id, username=username, first_name=first_name)
    
    # Показываем индикатор загрузки
    loading_msg = await message.answer(
        "🔄 Получаем ваш VPN ключ...",
        reply_markup=None
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
                from handlers.vpn_simplified import get_default_country
                default_country = await get_default_country()  # Первая доступная страна
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
            
            logger.info("VPN key provided to user via command", 
                       telegram_id=telegram_id,
                       key_id=vpn_key_data.get('id'))
        else:
            # Ошибка получения ключа
            await loading_msg.edit_text(
                get_no_key_error(),
                reply_markup=get_main_menu_keyboard()
            )
            
            logger.error("Failed to provide VPN key via command", telegram_id=telegram_id)
            
    except Exception as e:
        logger.error("Error in create_key command", 
                    telegram_id=telegram_id, 
                    error=str(e))
        
        await loading_msg.edit_text(
            get_no_key_error(),
            reply_markup=get_main_menu_keyboard()
        )

@commands_router.message(Command("refresh_key"))
async def cmd_refresh_key(message: types.Message):
    """Команда /refresh_key - обновить ключ с учетом назначенной страны"""
    telegram_id = message.from_user.id
    username = message.from_user.username or ""
    first_name = message.from_user.first_name or ""
    
    logger.info("Command /refresh_key called", user_id=telegram_id, username=username, first_name=first_name)
    
    # Показываем индикатор загрузки
    loading_msg = await message.answer(
        "🔄 Обновляем ваш VPN ключ...",
        reply_markup=None
    )
    
    try:
        # Используем новую логику создания ключа для назначенной страны
        from handlers.vpn_simplified import create_vpn_key_for_country
        
        new_key_result = await create_vpn_key_for_country(telegram_id)
        
        if new_key_result and new_key_result.get('success'):
            # Получаем новый ключ
            vless_url = new_key_result['vpn_key']['vless_url']
            
            # Используем расширенное сообщение с информацией о сервере
            try:
                from handlers.vpn_simplified import enhance_vpn_key_message
                message_text, keyboard = await enhance_vpn_key_message(
                    vless_url, 
                    telegram_id, 
                    is_update=True
                )
            except Exception as e:
                # Fallback к базовому шаблону с сервером
                from templates.messages import get_vpn_key_message_with_server
                from handlers.vpn_simplified import get_default_country
                default_country = await get_default_country()  # Первая доступная страна
                message_text = get_vpn_key_message_with_server(
                    vless_url, 
                    default_country, 
                    is_update=True
                )
                keyboard = get_main_menu_keyboard()
            
            await loading_msg.edit_text(
                message_text,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
            
            logger.info("VPN key refreshed successfully via command", user_id=telegram_id)
        else:
            # Ошибка создания нового ключа
            error_msg = new_key_result.get('error', 'Неизвестная ошибка') if new_key_result else 'API недоступен'
            
            await loading_msg.edit_text(
                f"❌ Не удалось обновить VPN ключ\n\n"
                f"Причина: {error_msg}\n\n"
                f"Попробуйте еще раз или обратитесь в поддержку",
                parse_mode="Markdown",
                reply_markup=get_main_menu_keyboard()
            )
            
            logger.error("Failed to refresh VPN key via command", 
                        user_id=telegram_id, 
                        error=error_msg)
            
    except Exception as e:
        logger.error("Error in refresh_key command",
                    user_id=telegram_id, 
                    error=str(e))
        
        await loading_msg.edit_text(
            "❌ Произошла ошибка при обновлении ключа\n\n"
            "Попробуйте еще раз или обратитесь в поддержку",
            parse_mode="Markdown", 
            reply_markup=get_main_menu_keyboard()
        )

@commands_router.message(Command("download_apps"))
async def cmd_download_apps(message: types.Message):
    """Команда /download_apps - скачать приложения"""
    logger.info("Command /download_apps called", user_id=message.from_user.id)
    
    await message.answer(
        get_download_apps_message(),
        parse_mode="Markdown", 
        reply_markup=get_main_menu_keyboard(),
        disable_web_page_preview=True
    )

@commands_router.message(Command("support"))
async def cmd_support(message: types.Message):
    """Команда /support - служба поддержки"""
    logger.info("Command /support called", user_id=message.from_user.id)
    
    await message.answer(
        get_support_message(),
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard()
    )

@commands_router.message(Command("subscription"))
async def cmd_subscription(message: types.Message):
    """Команда /subscription - управление подпиской"""
    logger.info("Command /subscription called", user_id=message.from_user.id)
    
    try:
        # Импортируем функцию получения клавиатуры подписки
        from keyboards.main_menu import get_subscription_keyboard_with_autopay
        
        # Получаем клавиатуру с планами подписки
        subscription_keyboard = await get_subscription_keyboard_with_autopay()
        
        subscription_message = """📋 **Управление подпиской**

Выберите подходящий план подписки для доступа к VPN сервису:

🔹 **1 месяц** - для краткосрочного использования
🔹 **3 месяца** - популярный выбор с выгодой
🔹 **6 месяцев** - максимальная экономия

✅ Безлимитный трафик
✅ Высокая скорость подключения  
✅ Серверы в разных странах
✅ Техническая поддержка 24/7"""

        await message.answer(
            subscription_message,
            parse_mode="Markdown",
            reply_markup=subscription_keyboard
        )
        
    except Exception as e:
        logger.error("Error in subscription command", error=str(e))
        
        # Fallback сообщение
        await message.answer(
            "📋 **Управление подпиской**\n\n"
            "Для управления подпиской используйте кнопку 'Подписка' в главном меню.",
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard()
        ) 