"""
Обработчики для упрощенного VPN бота (4 основные функции)
"""

import structlog
from aiogram import types, F, Router
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
router = Router()

@router.callback_query(F.data == "create_or_remind_key")
async def handle_create_or_remind_key(callback: types.CallbackQuery):
    """Обработчик кнопки 'Создать/напомнить ключ'"""
    await callback.answer()
    
    telegram_id = callback.from_user.id
    username = callback.from_user.username or ""
    first_name = callback.from_user.first_name or ""
    
    logger.info("User requested VPN key", telegram_id=telegram_id, username=username, first_name=first_name)
    
    # Показываем индикатор загрузки
    loading_msg = await callback.message.edit_text(
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
        logger.error("Error in create_or_remind_key handler", 
                    telegram_id=telegram_id, 
                    error=str(e))
        
        await loading_msg.edit_text(
            get_no_key_error(),
            reply_markup=get_main_menu_keyboard()
        )

@router.callback_query(F.data == "refresh_key")
async def handle_refresh_key(callback: types.CallbackQuery):
    """Обработчик кнопки 'Обновить ключ'"""
    await callback.answer()
    
    telegram_id = callback.from_user.id
    username = callback.from_user.username or ""
    first_name = callback.from_user.first_name or ""
    
    logger.info("User requested VPN key refresh", telegram_id=telegram_id, username=username, first_name=first_name)
    
    # Показываем индикатор загрузки
    loading_msg = await callback.message.edit_text(
        "🔄 Обновляем ваш VPN ключ...\n"
        "⏳ Это может занять до 15 секунд",
        reply_markup=None
    )
    
    try:
        # Обновляем ключ через VPN менеджер
        vpn_key_data = await vpn_manager.update_user_key(telegram_id, username, first_name)
        
        if vpn_key_data and vpn_key_data.get('vless_url'):
            # Используем ту же логику, что и в команде /refresh_key (работающая)
            message_text = get_vpn_key_message(vpn_key_data['vless_url'], is_update=True)
            
            # Отправляем сообщение с новым ключом
            await loading_msg.edit_text(
                message_text,
                parse_mode="Markdown",
                reply_markup=get_main_menu_keyboard(),
                disable_web_page_preview=True
            )
            
            logger.info("VPN key refreshed successfully", telegram_id=telegram_id)
        else:
            # Ошибка обновления ключа - используем ту же логику, что и в команде
            await loading_msg.edit_text(
                get_key_update_error(),
                reply_markup=get_main_menu_keyboard()
            )
            
            logger.error("Failed to refresh VPN key via callback", telegram_id=telegram_id)
    except Exception as e:
        logger.error("Error during VPN key refresh", 
                    telegram_id=telegram_id, 
                    error=str(e))
        
        await loading_msg.edit_text(
            get_key_update_error(),
            reply_markup=get_main_menu_keyboard()
        )

@router.callback_query(F.data == "download_apps")
async def handle_download_apps(callback: types.CallbackQuery):
    """Обработчик кнопки 'Скачать приложение'"""
    await callback.answer()
    
    logger.info("User requested download apps", telegram_id=callback.from_user.id)
    
    await callback.message.edit_text(
        get_download_apps_message(),
        parse_mode="Markdown", 
        reply_markup=get_main_menu_keyboard(),
        disable_web_page_preview=True
    )