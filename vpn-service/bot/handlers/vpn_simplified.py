"""
Обработчики для упрощенного VPN бота (4 основные функции)
С проверкой подписки перед выдачей VPN ключей
"""

import structlog
import sys
import os
from aiogram import types, F, Router

# Добавляем путь к backend для импорта сервисов
sys.path.append(os.path.join(os.path.dirname(__file__), '../../backend'))

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

# Импортируем VPN Access Control
try:
    from services.vpn_access_control_service import check_user_vpn_access
    from config.database import get_db
    VPN_ACCESS_CONTROL_AVAILABLE = True
    logger.info("VPN Access Control loaded successfully")
except ImportError as e:
    logger.warning("VPN Access Control not available", error=str(e))
    VPN_ACCESS_CONTROL_AVAILABLE = False
router = Router()

async def check_vpn_access(telegram_id: int) -> dict:
    """Проверка доступа к VPN через VPNAccessControlService"""
    try:
        if not VPN_ACCESS_CONTROL_AVAILABLE:
            logger.warning("VPN Access Control not available", telegram_id=telegram_id)
            return {"has_access": True, "reason": "no_access_control"}
        
        # Получаем сессию БД
        async for db_session in get_db():
            try:
                result = await check_user_vpn_access(db_session, telegram_id)
                logger.info("VPN access check completed", 
                           telegram_id=telegram_id,
                           has_access=result.get("has_access"),
                           reason=result.get("reason"))
                return result
            except Exception as e:
                logger.error("Error during VPN access check", 
                           telegram_id=telegram_id,
                           error=str(e))
                # В случае ошибки разрешаем доступ (fail-open)
                return {"has_access": True, "reason": "check_error"}
            finally:
                break  # Выходим из async generator
                
    except Exception as e:
        logger.error("Critical error in VPN access check", 
                   telegram_id=telegram_id,
                   error=str(e))
        # В случае критической ошибки разрешаем доступ (fail-open)
        return {"has_access": True, "reason": "critical_error"}

async def show_subscription_required_message(message, access_result: dict):
    """Показать сообщение о необходимости подписки с планами"""
    try:
        
        reason = access_result.get("reason", "no_subscription")
        days_remaining = access_result.get("days_remaining", 0)
        
        if reason == "no_subscription":
            if days_remaining > 0:
                # Подписка истекла недавно
                message_text = (
                    f"⏰ **Ваша подписка истекла {abs(days_remaining)} дн. назад**\n\n"
                    "🔐 Для получения VPN ключа необходимо продлить подписку\n\n"
                    "📊 Выберите подходящий план:"
                )
            else:
                # Нет подписки вообще
                message_text = (
                    "🔐 **Для получения VPN ключа необходима активная подписка**\n\n"
                    "📊 Выберите подходящий план:"
                )
        elif reason == "user_not_found":
            message_text = (
                "❌ **Пользователь не найден в системе**\n\n"
                "Пожалуйста, обратитесь в поддержку или попробуйте позже."
            )
        else:
            message_text = (
                "❌ **Доступ к VPN временно недоступен**\n\n"
                f"Причина: {access_result.get('message', 'Неизвестная ошибка')}"
            )
        
        # Создаем клавиатуру с планами подписки
        if reason in ["no_subscription"]:
            try:
                from keyboards.main_menu import get_subscription_keyboard_with_autopay
                keyboard = await get_subscription_keyboard_with_autopay()
            except Exception as e:
                logger.error("Error creating subscription keyboard", error=str(e))
                keyboard = get_main_menu_keyboard()
        else:
            keyboard = get_main_menu_keyboard()
        
        await message.edit_text(
            message_text,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
        
        logger.info("Subscription required message shown", 
                   reason=reason,
                   days_remaining=days_remaining)
        
    except Exception as e:
        logger.error("Error showing subscription required message", error=str(e))
        
        # Fallback сообщение
        await message.edit_text(
            "🔐 **Для использования VPN необходима активная подписка**\n\n"
            "Перейдите в раздел 'Подписка' для оформления.",
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard()
        )

@router.callback_query(F.data == "create_or_remind_key")
async def handle_create_or_remind_key(callback: types.CallbackQuery):
    """Обработчик кнопки 'Создать/напомнить ключ' с проверкой подписки"""
    await callback.answer()
    
    telegram_id = callback.from_user.id
    username = callback.from_user.username or ""
    first_name = callback.from_user.first_name or ""
    
    logger.info("User requested VPN key", telegram_id=telegram_id, username=username, first_name=first_name)
    
    # Показываем индикатор загрузки
    loading_msg = await callback.message.edit_text(
        "🔄 Проверяем доступ к VPN...",
        reply_markup=None
    )
    
    try:
        # НОВОЕ: Проверка доступа к VPN на основе подписки
        if VPN_ACCESS_CONTROL_AVAILABLE:
            access_result = await check_vpn_access(telegram_id)
            
            if not access_result.get("has_access", False):
                # Доступ запрещен - показываем планы подписки
                await show_subscription_required_message(loading_msg, access_result)
                return
        else:
            logger.warning("VPN Access Control not available, proceeding without check", telegram_id=telegram_id)
        
        # Обновляем сообщение о загрузке
        await loading_msg.edit_text("🔄 Получаем ваш VPN ключ...")
        
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
    """Обработчик кнопки 'Обновить ключ' с проверкой подписки"""
    await callback.answer()
    
    telegram_id = callback.from_user.id
    username = callback.from_user.username or ""
    first_name = callback.from_user.first_name or ""
    
    logger.info("User requested VPN key refresh", telegram_id=telegram_id, username=username, first_name=first_name)
    
    # Показываем индикатор загрузки
    loading_msg = await callback.message.edit_text(
        "🔄 Проверяем доступ к VPN...",
        reply_markup=None
    )
    
    try:
        # НОВОЕ: Проверка доступа к VPN на основе подписки
        if VPN_ACCESS_CONTROL_AVAILABLE:
            access_result = await check_vpn_access(telegram_id)
            
            if not access_result.get("has_access", False):
                # Доступ запрещен - показываем планы подписки
                await show_subscription_required_message(loading_msg, access_result)
                return
        else:
            logger.warning("VPN Access Control not available, proceeding without check", telegram_id=telegram_id)
        
        # Обновляем сообщение о загрузке
        await loading_msg.edit_text(
            "🔄 Обновляем ваш VPN ключ...\n"
            "⏳ Это может занять до 15 секунд"
        )
        
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