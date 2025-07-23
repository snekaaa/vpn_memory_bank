from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
# from api_client import api_client  # Убрано - заменено на прямые HTTP запросы
import aiohttp
import structlog
from typing import List, Optional

logger = structlog.get_logger(__name__)


def get_back_to_menu_keyboard() -> InlineKeyboardMarkup:
    """Inline клавиатура для возврата в главное меню"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="🏠 Главное меню",
                callback_data="back_to_main_menu"
            )]
        ]
    )


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Главное меню бота (только кнопка обновления)"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔄 Обновить ключ",
                    callback_data="refresh_key"
                )
            ]
        ]
    )
    return keyboard


def get_vpn_key_keyboard_with_countries(current_country_code: str, available_countries: List[dict]) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру с кнопкой обновления ключа и выбором стран (вертикальный макет)
    
    Args:
        current_country_code: ISO код текущей страны пользователя
        available_countries: Список стран с ключами {id, code, name, flag_emoji, is_active}
    
    Returns:
        InlineKeyboardMarkup с вертикальным расположением кнопок стран
    """
    buttons = []
    
    # Первая кнопка - обновление ключа
    buttons.append([
        InlineKeyboardButton(
            text="🔄 Обновить ключ",
            callback_data="refresh_key"
        )
    ])
    
    # Добавляем кнопки для каждой страны
    for country in available_countries:
        country_code = country['code']
        country_name = country['name']
        flag_emoji = country['flag_emoji']
        
        # Определяем, является ли эта страна текущей
        is_current = country_code == current_country_code
        
        # Формируем текст кнопки
        if is_current:
            # Текущая страна - показываем с галочкой и делаем disabled (не кликабельной)
            button_text = f"{flag_emoji} {country_name} ✓"
            # Для текущей страны используем callback, который не будет обрабатываться
            callback_data = f"current_country:{country_code}"
        else:
            # Другие страны - обычные кнопки переключения
            button_text = f"{flag_emoji} {country_name}"
            callback_data = f"switch_country:{country_code}"
        
        # Добавляем кнопку страны в отдельной строке (вертикальный макет)
        buttons.append([
            InlineKeyboardButton(
                text=button_text,
                callback_data=callback_data
            )
        ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_country_selection_loading_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру во время переключения сервера (показывает процесс)
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="⏳ Переключение сервера...",
                callback_data="switching_in_progress"
            )]
        ]
    )


def get_country_fallback_keyboard(available_countries: List[dict]) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для выбора fallback страны когда основная недоступна
    
    Args:
        available_countries: Список доступных стран для fallback
    """
    buttons = []
    
    # Добавляем текст с предупреждением
    buttons.append([
        InlineKeyboardButton(
            text="⚠️ Выберите альтернативный сервер:",
            callback_data="fallback_info"
        )
    ])
    
    # Добавляем доступные страны
    for country in available_countries:
        button_text = f"{country['flag_emoji']} {country['name']}"
        callback_data = f"switch_country:{country['code']}"
        
        buttons.append([
            InlineKeyboardButton(
                text=button_text,
                callback_data=callback_data
            )
        ])
    
    # Кнопка отмены
    buttons.append([
        InlineKeyboardButton(
            text="❌ Отмена",
            callback_data="cancel_country_switch"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def get_subscription_keyboard_with_autopay() -> InlineKeyboardMarkup:
    """Создает клавиатуру выбора подписки с опцией автоплатежа"""
    from services.plans_api_client import plans_api_client
    
    buttons = []
    
    try:
        # Получаем планы из API
        subscription_plans = await plans_api_client.get_plans()
        
        for plan_id, plan in subscription_plans.items():
            # Кнопка обычной оплаты
            discount_text = f" (-{plan['discount']})" if plan.get('discount') else ""
            button_text = f"{plan['name']} - {plan['price']}₽{discount_text}"
            buttons.append([InlineKeyboardButton(
                text=button_text,
                callback_data=f"pay:{plan_id}"
            )])
            
            # Кнопка с автоплатежом (только для не-триальных планов)
            if plan_id != "trial":
                autopay_text = f"⚡ {plan['name']} + Автоплатеж - {plan['price']}₽"
                buttons.append([InlineKeyboardButton(
                    text=autopay_text,
                    callback_data=f"pay_autopay:{plan_id}"
                )])
    except Exception as e:
        logger.error(f"Error loading subscription plans: {e}")
        # В случае ошибки показываем кнопку "Попробовать позже"
        buttons.append([InlineKeyboardButton(
            text="⚠️ Планы временно недоступны",
            callback_data="plans_unavailable"
        )])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def get_subscription_keyboard_without_cancel() -> InlineKeyboardMarkup:
    """Создает клавиатуру выбора подписки БЕЗ кнопки отмены"""
    from services.plans_api_client import plans_api_client
    
    buttons = []
    
    try:
        # Получаем планы из API
        subscription_plans = await plans_api_client.get_plans()
        
        for plan_id, plan in subscription_plans.items():
            discount_text = f" (-{plan['discount']})" if plan.get('discount') else ""
            button_text = f"{plan['name']} - {plan['price']}₽{discount_text}"
            buttons.append([InlineKeyboardButton(
                text=button_text,
                callback_data=f"pay:{plan_id}"
            )])
    except Exception as e:
        logger.error(f"Error loading subscription plans: {e}")
        # В случае ошибки показываем кнопку "Попробовать позже"
        buttons.append([InlineKeyboardButton(
            text="⚠️ Планы временно недоступны",
            callback_data="plans_unavailable"
        )])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def get_subscription_keyboard_with_autopay_toggle(autopay_enabled: bool = True) -> InlineKeyboardMarkup:
    """Создает клавиатуру выбора подписки с кнопкой переключения автопродления"""
    from services.plans_api_client import plans_api_client
    
    buttons = []
    
    # Кнопка переключения автопродления
    if autopay_enabled:
        autopay_text = "⚡ Автопродление (вкл)"
        autopay_callback = "toggle_autopay_off"
    else:
        autopay_text = "❌ Автопродление (выкл)"
        autopay_callback = "toggle_autopay_on"
    
    buttons.append([InlineKeyboardButton(
        text=autopay_text,
        callback_data=autopay_callback
    )])
    
    try:
        # Получаем планы из API
        subscription_plans = await plans_api_client.get_plans()
        
        for plan_id, plan in subscription_plans.items():
            discount_text = f" (-{plan['discount']})" if plan.get('discount') else ""
            
            # Если автопродление включено - показываем планы с автоплатежом
            # Если выключено - показываем обычные планы
            if autopay_enabled:
                if plan_id != "trial":  # Триал не поддерживает автоплатеж
                    button_text = f"⚡ {plan['name']} - {plan['price']}₽{discount_text}"
                    callback_data = f"pay_autopay:{plan_id}"
                else:
                    button_text = f"{plan['name']} - {plan['price']}₽{discount_text}"
                    callback_data = f"pay:{plan_id}"
            else:
                button_text = f"{plan['name']} - {plan['price']}₽{discount_text}"
                callback_data = f"pay:{plan_id}"
            
            buttons.append([InlineKeyboardButton(
                text=button_text,
                callback_data=callback_data
            )])
    except Exception as e:
        logger.error(f"Error loading subscription plans: {e}")
        # В случае ошибки показываем кнопку "Попробовать позже"
        buttons.append([InlineKeyboardButton(
            text="⚠️ Планы временно недоступны",
            callback_data="plans_unavailable"
        )])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_payment_confirmation_keyboard_back_only(plan_id: str) -> InlineKeyboardMarkup:
    """Создает клавиатуру подтверждения платежа ТОЛЬКО с кнопкой Назад"""
    buttons = [
        [InlineKeyboardButton(
            text="💳 Оплатить",
            callback_data=f"confirm_pay:{plan_id}"
        )],
        [InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data="select_subscription"
        )]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_existing_payment_keyboard(payment_id: int, payment_url: str) -> InlineKeyboardMarkup:
    """Создает клавиатуру для существующего платежа с кнопками оплатить и отменить"""
    buttons = [
        [InlineKeyboardButton(
            text="💳 Перейти к оплате",
            url=payment_url
        )],
        [InlineKeyboardButton(
            text="🔄 Проверить статус",
            callback_data=f"check_payment:{payment_id}"
        )],
        [InlineKeyboardButton(
            text="❌ Отменить счет",
            callback_data="cancel_payment"
        )]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def _make_api_request(endpoint: str) -> dict:
    """Простой HTTP запрос к backend API"""
    try:
        async with aiohttp.ClientSession() as session:
            url = f"http://backend:8000{endpoint}"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=3)) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error("API request failed", endpoint=endpoint, status=response.status)
                    return {}
    except Exception as e:
        logger.error("API request error", endpoint=endpoint, error=str(e))
        return {}


async def get_user_subscription_days(telegram_id: int, user_data: dict = None) -> int:
    """Получить количество дней до окончания подписки пользователя"""
    try:
        logger.info("🔍 Получаем данные пользователя для подсчета дней подписки", telegram_id=telegram_id)
        
        # Получаем данные пользователя из API через прямой HTTP запрос
        user_data_to_use = user_data if user_data else await _make_api_request(f"/api/v1/integration/user-dashboard/{telegram_id}")
        
        if not user_data_to_use or not user_data_to_use.get('success'):
            logger.warning("❌ Пользователь не найден в API, создаем нового", telegram_id=telegram_id)
            
            # Создаем нового пользователя через full-cycle API
            try:
                from services.vpn_manager_x3ui import vpn_manager_x3ui as vpn_manager
                
                # Используем переданные данные пользователя или пустые строки
                if user_data:
                    username = user_data.get("username", "")
                    first_name = user_data.get("first_name", "")
                else:
                    username = ""
                    first_name = ""
                
                # Создаем пользователя через VPN manager с правильными данными
                user_result = await vpn_manager.get_or_create_user_key(telegram_id, username, first_name)
                
                if user_result and user_result.get('success'):
                    logger.info("✅ Новый пользователь создан", telegram_id=telegram_id)
                    
                    # Используем данные из результата создания вместо повторного API запроса
                    if user_result.get('source') == 'FULL_CYCLE_NEW_USER':
                        # Новый пользователь создан - проверяем настройки триала через API
                        logger.info("✅ Новый пользователь создан, проверяем настройки триала", telegram_id=telegram_id)
                        
                        # Получаем настройки приложения через API
                        try:
                            settings_data = await _make_api_request("/api/v1/integration/app-settings")
                            if settings_data and settings_data.get('success'):
                                settings = settings_data.get('settings', {})
                                trial_enabled = settings.get('trial_enabled', False)
                                trial_days = settings.get('trial_days', 0)
                                
                                if trial_enabled and trial_days > 0:
                                    logger.info("✅ Триал включен в настройках", 
                                               telegram_id=telegram_id,
                                               trial_days=trial_days)
                                    return trial_days
                                else:
                                    logger.info("ℹ️ Триал выключен в настройках", 
                                               telegram_id=telegram_id,
                                               trial_enabled=trial_enabled,
                                               trial_days=trial_days)
                                    return 0
                            else:
                                logger.warning("⚠️ Не удалось получить настройки, используем 0 дней", 
                                             telegram_id=telegram_id)
                                return 0
                        except Exception as settings_error:
                            logger.error("❌ Ошибка получения настроек триала", 
                                        telegram_id=telegram_id,
                                        error=str(settings_error))
                            return 0
                    else:
                        # Существующий пользователь - запрашиваем актуальные данные
                        user_data_to_use = await _make_api_request(f"/api/v1/integration/user-dashboard/{telegram_id}")
                else:
                    logger.error("❌ Не удалось создать пользователя", telegram_id=telegram_id, error=user_result.get('error', 'Unknown error'))
                    return 0
                    
            except Exception as create_error:
                logger.error("❌ Ошибка создания пользователя", telegram_id=telegram_id, error=str(create_error))
                return 0
        
        if not user_data_to_use or not user_data_to_use.get('success'):
            logger.warning("❌ Пользователь не найден в API", telegram_id=telegram_id)
            return 0
        
        user_info = user_data_to_use.get('user', {})
        
        logger.info("✅ Данные пользователя получены", 
                   telegram_id=telegram_id,
                   subscription_status=user_info.get('subscription_status'),
                   valid_until=user_info.get('valid_until'))
        
        # Проверяем статус подписки и дату окончания
        subscription_status = user_info.get('subscription_status', 'none')
        valid_until = user_info.get('valid_until')
        
        if subscription_status != 'active':
            logger.info("ℹ️ Подписка не активна", 
                       telegram_id=telegram_id, 
                       status=subscription_status)
            return 0
            
        if not valid_until:
            logger.warning("⚠️ Дата окончания подписки не указана", telegram_id=telegram_id)
            return 0
        
        # Вычисляем количество дней до окончания
        from datetime import datetime, timezone
        
        try:
            # Парсим дату окончания подписки
            try:
                import dateutil.parser
                end_date = dateutil.parser.parse(valid_until)
            except ImportError:
                # Если dateutil недоступен, парсим вручную
                if valid_until.endswith('Z'):
                    end_date = datetime.fromisoformat(valid_until[:-1] + '+00:00')
                elif '+' in valid_until or valid_until.endswith('00:00'):
                    end_date = datetime.fromisoformat(valid_until)
                else:
                    end_date = datetime.fromisoformat(valid_until + '+00:00')
            
            # Убеждаемся что дата в UTC
            if end_date.tzinfo is None:
                end_date = end_date.replace(tzinfo=timezone.utc)
                
            logger.info("📅 Дата окончания подписки распознана", 
                       telegram_id=telegram_id,
                       end_date=end_date.isoformat())
            
            # Вычисляем разность с текущим временем
            now = datetime.now(timezone.utc)
            delta = end_date - now
            
            # Возвращаем количество дней (минимум 0)
            days_remaining = max(0, delta.days)
            
            logger.info("🎯 Подсчет дней завершен", 
                       telegram_id=telegram_id,
                       days_remaining=days_remaining,
                       now=now.isoformat(),
                       delta_days=delta.days)
            
            return days_remaining
            
        except Exception as date_error:
            logger.error("❌ Ошибка парсинга даты", 
                        telegram_id=telegram_id,
                        valid_until=valid_until,
                        error=str(date_error))
            return 0
        
    except Exception as e:
        logger.error("💥 Общая ошибка получения дней подписки", 
                    telegram_id=telegram_id, 
                    error=str(e))
        return 0

async def send_main_menu(message, telegram_id, text="🏠 Главное меню", user_data=None):
    """Отправить главное меню пользователю"""
    try:
        # Получаем количество дней подписки с передачей данных пользователя
        days_remaining = await get_user_subscription_days(telegram_id, user_data)
        
        # Создаем клавиатуру главного меню
        keyboard = get_main_menu(days_remaining, days_remaining > 0)
        
        # Отправляем сообщение с клавиатурой
        await message.answer(text, reply_markup=keyboard, parse_mode='Markdown')
        
    except Exception as e:
        logger.error("Error sending main menu", telegram_id=telegram_id, error=str(e))
        # Fallback - отправляем без клавиатуры
        await message.answer(text, parse_mode='Markdown')

def get_main_menu(days_remaining: int = 0, has_active_subscription: bool = True) -> ReplyKeyboardMarkup:
    """Главное меню с кнопками для быстрого доступа"""
    
    # Формируем текст кнопки подписки в зависимости от количества дней
    if days_remaining > 0:
        subscription_text = f"💳 Подписка {days_remaining} дней"
    else:
        subscription_text = "💳 Подписка"
    
    # Первая строка кнопок - условно показываем VPN кнопку
    first_row = []
    
    if has_active_subscription:
        # Пользователь с активной подпиской - показываем кнопку VPN ключа
        first_row.append(KeyboardButton(text="🔑 Мой VPN ключ"))
    else:
        # Пользователь без подписки - показываем кнопку получения доступа
        first_row.append(KeyboardButton(text="🔐 Получить VPN доступ"))
    
    first_row.append(KeyboardButton(text=subscription_text))
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            first_row,
            [
                KeyboardButton(text="📱 Приложения"),
                KeyboardButton(text="🧑🏼‍💻 Служба поддержки")
            ],
            [
                KeyboardButton(text="📄 Оферта и Политика конфиденциальности")
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return keyboard 