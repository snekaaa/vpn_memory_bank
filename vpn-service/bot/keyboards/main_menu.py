from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
# from api_client import api_client  # Убрано - заменено на прямые HTTP запросы
import aiohttp
import structlog

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
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error("API request failed", endpoint=endpoint, status=response.status)
                    return {}
    except Exception as e:
        logger.error("API request error", endpoint=endpoint, error=str(e))
        return {}


async def get_user_subscription_days(telegram_id: int) -> int:
    """Получить количество дней до окончания подписки пользователя"""
    try:
        logger.info("🔍 Получаем данные пользователя для подсчета дней подписки", telegram_id=telegram_id)
        
        # Получаем данные пользователя из API через прямой HTTP запрос
        user_data = await _make_api_request(f"/api/v1/integration/user-dashboard/{telegram_id}")
        
        if not user_data or not user_data.get('success'):
            logger.warning("❌ Пользователь не найден в API", telegram_id=telegram_id)
            return 0
        
        user_info = user_data.get('user', {})
        
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

async def send_main_menu(message, telegram_id, text="🏠 Главное меню"):
    """Универсальный хелпер для отправки главного меню с актуальным количеством дней подписки"""
    days_remaining = await get_user_subscription_days(telegram_id)
    await message.answer(
        text,
        reply_markup=get_main_menu(days_remaining)
    )

def get_main_menu(days_remaining: int = 0) -> ReplyKeyboardMarkup:
    """Главное меню с кнопками для быстрого доступа"""
    
    # Формируем текст кнопки подписки в зависимости от количества дней
    if days_remaining > 0:
        subscription_text = f"💳 Подписка {days_remaining} дней"
    else:
        subscription_text = "💳 Подписка"
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🔑 Мой VPN ключ"),
                KeyboardButton(text=subscription_text)
            ],
            [
                KeyboardButton(text="📱 Приложения"),
                KeyboardButton(text="🧑🏼‍💻 Служба поддержки")
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return keyboard 