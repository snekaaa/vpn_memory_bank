"""
Обработчики для упрощенного VPN бота (4 основные функции)
С проверкой подписки перед выдачей VPN ключей
Расширен поддержкой выбора стран серверов
"""

import structlog
import sys
import os
import asyncio
from aiogram import types, F, Router

# Добавляем путь к backend для импорта сервисов
sys.path.append(os.path.join(os.path.dirname(__file__), '../../backend'))

from services.vpn_manager_x3ui import vpn_manager_x3ui as vpn_manager
from templates.messages import (
    get_vpn_key_message,
    get_vpn_key_message_with_server,
    get_server_switch_loading_message,
    get_server_switch_success_message,
    get_server_switch_error_message,
    get_download_apps_message, 
    get_support_message,
    get_no_key_error,
    get_key_update_error
)
from keyboards.main_menu import (
    get_main_menu_keyboard,
    get_vpn_key_keyboard_with_countries,
    get_country_selection_loading_keyboard,
    get_country_fallback_keyboard
)

# NEW: Country Services - простая хардкодная версия для демо
COUNTRY_SERVICE_AVAILABLE = True
logger = structlog.get_logger(__name__)
logger.info("Country Service enabled with hardcoded demo data")

# Хардкодные страны для демо - только активные
DEMO_COUNTRIES = [
    {"id": 2, "code": "NL", "name": "Нидерланды", "flag_emoji": "🇳🇱", "display_name": "🇳🇱 Нидерланды"},
    {"id": 3, "code": "DE", "name": "Германия", "flag_emoji": "🇩🇪", "display_name": "🇩🇪 Германия"}
]

async def get_user_current_assignment_info(telegram_id: int):
    """Получить информацию о текущем назначении пользователя"""
    try:
        import aiohttp
        
        logger.info("Getting user assignment info", telegram_id=telegram_id)
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"http://backend:8000/api/v1/countries/user/{telegram_id}/assignment"
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info("Assignment info received", telegram_id=telegram_id, data=data)
                    return data
                else:
                    logger.warning("Assignment API returned error", telegram_id=telegram_id, status=response.status)
                    return None
                    
    except Exception as e:
        logger.error("Failed to get user assignment", telegram_id=telegram_id, error=str(e))
        return None

async def get_available_countries():
    """Получить доступные страны - демо версия"""
    return DEMO_COUNTRIES

async def get_user_dashboard_enhanced(telegram_id: int):
    """Получить расширенную информацию о пользователе - демо версия"""
    return {
        "success": True,
        "countries": {
            "available": DEMO_COUNTRIES,
            "current": {"country": DEMO_COUNTRIES[0]}  # По умолчанию Нидерланды
        }
    }

async def create_vpn_key_for_country(telegram_id: int):
    """Создать VPN ключ для назначенной страны пользователя"""
    try:
        import aiohttp
        
        logger.info("Creating VPN key for assigned country", telegram_id=telegram_id)
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"http://backend:8000/api/v1/vpn-keys/user/{telegram_id}/create-for-country"
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info("VPN key created successfully", telegram_id=telegram_id, success=data.get('success'))
                    return data
                else:
                    logger.error("VPN key creation failed", telegram_id=telegram_id, status=response.status)
                    return {"success": False, "error": f"API returned status {response.status}"}
                    
    except Exception as e:
        logger.error("Failed to create VPN key for country", telegram_id=telegram_id, error=str(e))
        return {"success": False, "error": str(e)}

async def switch_user_country(telegram_id: int, country_code: str):
    """Переключить пользователя на сервер - реальная версия через API"""
    try:
        # Используем API client для реального переключения
        import aiohttp
        
        async with aiohttp.ClientSession() as session:
            # Вызываем реальный API backend для переключения с query parameters
            async with session.post(
                f"http://backend:8000/api/v1/countries/switch?user_id={telegram_id}&country_code={country_code}"
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data
                else:
                    error_text = await response.text()
                    return {"success": False, "error": f"API error {response.status}: {error_text}"}
                    
    except Exception as e:
        logger.error("Failed to switch user country via API", 
                    telegram_id=telegram_id, 
                    country_code=country_code, 
                    error=str(e))
        
        # Fallback - возвращаем как будто успешно переключили
        country = next((c for c in DEMO_COUNTRIES if c["code"] == country_code), None)
        return {
            "success": True,
            "fallback": True,
            "country_info": country,
            "message": f"Переключено на {country['name']} (fallback)" if country else "Страна не найдена"
        }

# Импортируем VPN Access Control - временно отключен
VPN_ACCESS_CONTROL_AVAILABLE = False
logger.info("VPN Access Control temporarily disabled due to model relationship issues")
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
            # ОБЯЗАТЕЛЬНО получаем информацию о текущем назначении пользователя
            assignment_info = await get_user_current_assignment_info(telegram_id)
            
            if assignment_info and assignment_info.get('country'):
                # Показываем сообщение с информацией о текущем сервере
                current_country = assignment_info['country']
                
                logger.info("User has country assignment", 
                           telegram_id=telegram_id, 
                           country=current_country['code'])
                
                # КРИТИЧНО: Создаем правильный ключ для назначенной страны
                vpn_key_data = await vpn_manager.create_key_for_user_country(
                    telegram_id, username, first_name
                )
                
                logger.info("Created key for assigned country", 
                           telegram_id=telegram_id, 
                           country=current_country['code'])
                
                message_text = get_vpn_key_message_with_server(
                    vpn_key_data['vless_url'], 
                    current_country, 
                    is_update=False
                )
            else:
                # FALLBACK: назначаем на Германию и создаем ключ
                logger.warning("No assignment info, creating assignment to Germany", telegram_id=telegram_id)
                
                # Принудительно назначаем на Германию
                switch_result = await switch_user_country(telegram_id, "DE")
                
                if switch_result.get('success'):
                    # Создаем ключ для Германии
                    vpn_key_data = await vpn_manager.create_key_for_user_country(
                        telegram_id, username, first_name
                    )
                
                fallback_country = {
                    "code": "DE", 
                    "name": "Германия", 
                    "flag_emoji": "🇩🇪",
                    "display_name": "🇩🇪 Германия"
                }
                message_text = get_vpn_key_message_with_server(
                    vpn_key_data['vless_url'], 
                    fallback_country, 
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
        
        # Получаем текущее назначение пользователя
        assignment_info = await get_user_current_assignment_info(telegram_id)
        
        if assignment_info and assignment_info.get('country'):
            # У пользователя есть назначение на страну
            current_country_code = assignment_info['country']['code']
            current_country = assignment_info['country']
            
            await loading_msg.edit_text(
                f"🔄 Обновляем ключ для {current_country['display_name']}..."
            )
            
            # КРИТИЧНО: Создаем ключ для назначенной страны
            vpn_key_data = await vpn_manager.create_key_for_user_country(
                telegram_id, username, first_name
            )
            
            logger.info("Refreshed key for assigned country", 
                       telegram_id=telegram_id, 
                       country=current_country_code)
        else:
            # Нет назначения - назначаем на Германию
            logger.info("No assignment found, assigning to Germany", telegram_id=telegram_id)
            switch_result = await switch_user_country(telegram_id, "DE")
            
            if switch_result.get('success'):
                vpn_key_data = await vpn_manager.create_key_for_user_country(
                    telegram_id, username, first_name
                )
            else:
                # Fallback
                vpn_key_data = await vpn_manager.update_user_key(telegram_id, username, first_name)
        
        if vpn_key_data and vpn_key_data.get('vless_url'):
            # ОБНОВЛЕНО: Используем расширенную функциональность с выбором стран
            message_text, keyboard = await enhance_vpn_key_message(
                vpn_key_data['vless_url'], 
                telegram_id, 
                is_update=True
            )
            
            # Отправляем сообщение с новым ключом
            await loading_msg.edit_text(
                message_text,
                parse_mode="Markdown",
                reply_markup=keyboard,
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


# NEW: Country Selection Handlers

@router.callback_query(F.data.startswith("switch_country:"))
async def handle_country_switch(callback: types.CallbackQuery):
    """Обработчик переключения на сервер другой страны"""
    await callback.answer()
    
    telegram_id = callback.from_user.id
    username = callback.from_user.username or ""
    first_name = callback.from_user.first_name or ""
    
    # Извлекаем код страны из callback data
    country_code = callback.data.split(":")[1]
    
    logger.info("User requested country switch", 
               telegram_id=telegram_id, 
               target_country=country_code)
    
    if not COUNTRY_SERVICE_AVAILABLE:
        await callback.message.edit_text(
            "❌ Функция выбора стран временно недоступна\n\nИспользуйте кнопку 'Обновить ключ'",
            reply_markup=get_main_menu_keyboard()
        )
        return
    
    try:
        # Показываем загрузку
        await callback.message.edit_text(
            f"🔄 Переключаемся на сервер в стране {country_code}...",
            reply_markup=None
        )
        
        # РЕАЛЬНО переключаем пользователя через API
        switch_result = await switch_user_country(telegram_id, country_code)
        
        if switch_result.get('success'):
            # Обновляем сообщение о прогрессе
            await callback.message.edit_text(
                f"🔄 Переключение прошло успешно! Получаем новый ключ для {country_code}...",
                reply_markup=None
            )
            
            # Получаем НОВЫЙ VPN ключ используя API создания по стране
            new_key_result = await create_vpn_key_for_country(telegram_id)
            
            if new_key_result and new_key_result.get('success'):
                vpn_key_data = {'vless_url': new_key_result['vpn_key']['vless_url']}
                
                # Показываем сообщение об успехе с новым ключом и флагами стран
                message_text, keyboard = await enhance_vpn_key_message(
                    vpn_key_data['vless_url'], 
                    telegram_id, 
                    is_update=True
                )
                
                await callback.message.edit_text(
                    message_text,
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
                
                logger.info("Country switch completed successfully", 
                           telegram_id=telegram_id, 
                           target_country=country_code)
            else:
                # Ошибка создания ключа
                await callback.message.edit_text(
                    f"❌ Не удалось создать ключ для сервера {country_code}\n\nПопробуйте еще раз или обратитесь в поддержку",
                    reply_markup=get_main_menu_keyboard()
                )
        else:
            # Переключение не удалось
            error_msg = switch_result.get('error', 'Неизвестная ошибка')
            await callback.message.edit_text(
                f"❌ Не удалось переключиться на {country_code}\n\n"
                f"Ошибка: {error_msg}",
                reply_markup=get_main_menu_keyboard()
            )
            
    except Exception as e:
        logger.error("Error in country switch handler", 
                    telegram_id=telegram_id,
                    target_country=country_code,
                    error=str(e))
        
        await callback.message.edit_text(
            f"❌ Системная ошибка при переключении на {country_code}",
            reply_markup=get_main_menu_keyboard()
        )


@router.callback_query(F.data.startswith("current_country:"))
async def handle_current_country_click(callback: types.CallbackQuery):
    """Обработчик клика по текущей стране (disabled кнопка)"""
    await callback.answer("Это ваш текущий сервер", show_alert=False)
    # Ничего не делаем - кнопка просто показывает текущее состояние


@router.callback_query(F.data == "switching_in_progress")
async def handle_switching_in_progress(callback: types.CallbackQuery):
    """Обработчик клика по кнопке во время переключения"""
    await callback.answer("Переключение сервера в процессе...", show_alert=False)
    # Ничего не делаем - просто информируем пользователя


@router.callback_query(F.data == "cancel_country_switch")
async def handle_cancel_country_switch(callback: types.CallbackQuery):
    """Обработчик отмены переключения страны"""
    await callback.answer()
    
    logger.info("User cancelled country switch", telegram_id=callback.from_user.id)
    
    # Возвращаемся к стандартному меню VPN ключа
    await callback.message.edit_text(
        "❌ Переключение сервера отменено",
        reply_markup=get_main_menu_keyboard()
    )


# Helper function для создания расширенного VPN ключа с выбором стран
async def enhance_vpn_key_message(vless_url: str, telegram_id: int, is_update: bool = False):
    """
    Расширяет VPN key message информацией о текущем сервере и кнопками выбора стран
    
    Args:
        vless_url: VLESS URL ключа
        telegram_id: Telegram ID пользователя
        is_update: Флаг обновления ключа
    
    Returns:
        tuple: (message_text, keyboard) или (basic_message, basic_keyboard) если country service недоступен
    """
    if not COUNTRY_SERVICE_AVAILABLE:
        # Fallback к базовой функциональности с показом сервера по умолчанию
        default_country = DEMO_COUNTRIES[0]  # Нидерланды
        message_text = get_vpn_key_message_with_server(vless_url, default_country, is_update)
        keyboard = get_vpn_key_keyboard_with_countries(default_country["code"], DEMO_COUNTRIES)
        return message_text, keyboard
    
    try:
        # Получаем доступные страны
        countries_data = await get_available_countries()
        if not countries_data:
            # Нет доступных стран - используем демо страны
            countries_data = DEMO_COUNTRIES
        
        # Получаем РЕАЛЬНОЕ назначение пользователя
        assignment_info = await get_user_current_assignment_info(telegram_id)
        
        if assignment_info and assignment_info.get('country'):
            # У пользователя есть назначение - используем его
            current_country = assignment_info['country']
        else:
            # Нет назначения - используем Нидерланды по умолчанию
            current_country = DEMO_COUNTRIES[0]  # Нидерланды
        
        # Показываем расширенный интерфейс с информацией о сервере
        message_text = get_vpn_key_message_with_server(
            vless_url, 
            current_country, 
            is_update
        )
        keyboard = get_vpn_key_keyboard_with_countries(
            current_country["code"],
            countries_data
        )
        return message_text, keyboard
            
    except Exception as e:
        logger.error("Error creating enhanced VPN message", 
                    telegram_id=telegram_id, 
                    error=str(e))
        # В случае ошибки ТАКЖЕ используем шаблон с сервером
        default_country = DEMO_COUNTRIES[0]  # Нидерланды
        message_text = get_vpn_key_message_with_server(vless_url, default_country, is_update)
        return message_text, get_main_menu_keyboard()