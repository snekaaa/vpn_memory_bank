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
            # Отправляем сообщение с ключом
            message_text = get_vpn_key_message(vpn_key_data['vless_url'], is_update=False)
            
            await loading_msg.edit_text(
                message_text,
                parse_mode="Markdown",
                reply_markup=get_main_menu_keyboard()
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
    """Команда /refresh_key - обновить ключ"""
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
        # Обновляем ключ через VPN менеджер
        vpn_key_data = await vpn_manager.update_user_key(telegram_id, username, first_name)
        
        if vpn_key_data and vpn_key_data.get('vless_url'):
            # Отправляем сообщение с обновленным ключом
            message_text = get_vpn_key_message(vpn_key_data['vless_url'], is_update=True)
            
            await loading_msg.edit_text(
                message_text,
                parse_mode="Markdown",
                reply_markup=get_main_menu_keyboard()
            )
            
            logger.info("VPN key refreshed for user via command", 
                       telegram_id=telegram_id,
                       key_id=vpn_key_data.get('id'))
        else:
            # Ошибка обновления ключа
            await loading_msg.edit_text(
                get_key_update_error(),
                reply_markup=get_main_menu_keyboard()
            )
            
            logger.error("Failed to refresh VPN key via command", telegram_id=telegram_id)
            
    except Exception as e:
        logger.error("Error in refresh_key command", 
                    telegram_id=telegram_id, 
                    error=str(e))
        
        await loading_msg.edit_text(
            get_key_update_error(),
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