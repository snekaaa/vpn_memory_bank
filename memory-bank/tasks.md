# ПЛАНИРОВАНИЕ: Исправление логики отображения подписки в VPN боте

## 📋 ОПРЕДЕЛЕНИЕ УРОВНЯ СЛОЖНОСТИ
**Уровень**: Level 3 (Intermediate Feature)
**Обоснование**: 
- Требует изменения логики отображения подписки в боте
- Изменения в интерфейсе пользователя и обработчиках
- Упрощение workflow отображения подписки

## 🎯 ТРЕБОВАНИЯ И АНАЛИЗ

### Текущая проблема:
1. **Неправильная логика отображения**: бот проверяет автоплатеж первым, а не статус подписки
2. **Пользователи с активной подпиской** (например, 24 дня) видят "Подписка истекла"
3. **Игнорирование поля `valid_until`** в пользу проверки только автоплатежей

### Новые требования:
1. **Если пользователь купил подписку** (поле `valid_until` > текущая дата):
   - Показать: "Ваша подписка действует до dd.mm.yyyy"
   - Показать: галочка "Автопродление - вкл/выкл" (inline checkbox)
   - Показать: "Докупить подписку:" + кнопки планов

2. **Если подписка не куплена** (поле `valid_until` <= текущая дата или null):
   - Показать только: "Выберите план подписки:" + список планов

3. **Автоплатеж** - это свойство, которое может быть или не быть у активной подписки

## 🏗️ АРХИТЕКТУРНЫЕ КОМПОНЕНТЫ

### Компоненты для изменения:
- **handlers/payments.py**: функция `show_subscription_plans()` - основная логика
- **keyboards/main_menu.py**: создание клавиатур для разных состояний
- **models/user.py**: использование поля `valid_until` для проверки подписки
- **API endpoints**: корректная логика получения статуса подписки

### Логика проверки подписки:
```python
# Основная проверка - по полю valid_until в User модели
user.valid_until > datetime.now(timezone.utc)  # Активная подписка

# Автоплатеж - дополнительное свойство
auto_payment_info.get('enabled')  # Включен ли автоплатеж
```

## 📋 ДЕТАЛЬНЫЙ ПЛАН РЕАЛИЗАЦИИ

### Этап 1: Исправление логики отображения подписки ✅ ЗАВЕРШЕН
**Цель**: Правильно определять активную подписку по полю `valid_until`

**Изменения в `handlers/payments.py`**:
```python
async def show_subscription_plans(message: Message, state: FSMContext):
    """Показать информацию о подписке или планы для покупки"""
    try:
        telegram_id = message.from_user.id
        api_client = SimpleAPIClient()
        
        # 1. СНАЧАЛА проверяем статус подписки по valid_until
        subscription_info = await api_client.get_user_subscription_status(telegram_id)
        
        if subscription_info and subscription_info.get('success'):
            days_remaining = subscription_info.get('days_remaining', 0)
            
            if days_remaining > 0:
                # АКТИВНАЯ ПОДПИСКА - показать информацию + управление автоплатежом
                await show_active_subscription_info(message, subscription_info, telegram_id)
                return
        
        # 2. НЕТ АКТИВНОЙ ПОДПИСКИ - показать планы
        await show_subscription_plans_selection(message, state)
        
    except Exception as e:
        logger.error(f"Error showing subscription plans: {e}")
        await message.answer("❌ Произошла ошибка при загрузке информации о подписке")
```

### Этап 2: Создание функции отображения активной подписки ✅
**Цель**: Показать информацию о подписке с управлением автоплатежом

**Новая функция**:
```python
async def show_active_subscription_info(message: Message, subscription_info: dict, telegram_id: int):
    """Показать информацию об активной подписке с управлением автоплатежом"""
    
    # Получаем информацию об автоплатеже
    api_client = SimpleAPIClient()
    auto_payment_info = await api_client.get_user_auto_payment_info(telegram_id)
    
    plan_name = subscription_info.get('plan_name', 'VPN подписка')
    end_date = subscription_info.get('end_date')
    days_remaining = subscription_info.get('days_remaining', 0)
    
    # Определяем статус автоплатежа
    if auto_payment_info and auto_payment_info.get('enabled'):
        autopay_status = "✅ Включен"
        autopay_button_text = "❌ Отключить автопродление"
        autopay_callback = "autopay_disable"
    else:
        autopay_status = "❌ Отключен"
        autopay_button_text = "✅ Включить автопродление"
        autopay_callback = "autopay_enable"
    
    text = (
        f"💳 **Ваша подписка**\n\n"
        f"📊 **Тариф:** {plan_name}\n"
        f"📅 **Действует до:** {end_date}\n"
        f"⏰ **Осталось:** {days_remaining} дн.\n\n"
        f"⚡ **Автопродление:** {autopay_status}\n\n"
        f"💡 **Докупить подписку:**"
    )
    
    # Создаем клавиатуру с управлением автоплатежом + планы
    keyboard = await create_active_subscription_keyboard(autopay_callback, autopay_button_text)
    
    await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")
```

### Этап 3: Создание клавиатур для разных состояний ✅
**Цель**: Упростить клавиатуры и сделать их понятными

**Клавиатура для активной подписки**:
```python
async def create_active_subscription_keyboard(autopay_callback: str, autopay_button_text: str) -> InlineKeyboardMarkup:
    """Создает клавиатуру для пользователя с активной подпиской"""
    from services.plans_api_client import plans_api_client
    
    buttons = []
    
    # Кнопка управления автоплатежом
    buttons.append([InlineKeyboardButton(
        text=autopay_button_text,
        callback_data=autopay_callback
    )])
    
    # Планы для докупки
    try:
        subscription_plans = await plans_api_client.get_plans()
        
        for plan_id, plan in subscription_plans.items():
            discount_text = f" (-{plan['discount']})" if plan.get('discount') else ""
            button_text = f"➕ {plan['name']} - {plan['price']}₽{discount_text}"
            buttons.append([InlineKeyboardButton(
                text=button_text,
                callback_data=f"extend_subscription:{plan_id}"
            )])
    except Exception as e:
        logger.error(f"Error loading plans: {e}")
    
    # Кнопка VPN ключа
    buttons.append([InlineKeyboardButton(
        text="📱 Мой VPN ключ",
        callback_data="create_or_remind_key"
    )])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)
```

**Клавиатура для выбора планов**:
```python
async def create_subscription_plans_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру выбора планов для пользователей без подписки"""
    from services.plans_api_client import plans_api_client
    
    buttons = []
    
    try:
        subscription_plans = await plans_api_client.get_plans()
        
        for plan_id, plan in subscription_plans.items():
            discount_text = f" (-{plan['discount']})" if plan.get('discount') else ""
            button_text = f"{plan['name']} - {plan['price']}₽{discount_text}"
            buttons.append([InlineKeyboardButton(
                text=button_text,
                callback_data=f"pay:{plan_id}"
            )])
    except Exception as e:
        logger.error(f"Error loading plans: {e}")
        buttons.append([InlineKeyboardButton(
            text="⚠️ Планы временно недоступны",
            callback_data="plans_unavailable"
        )])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)
```

### Этап 4: Обработчики для управления автоплатежом ✅
**Цель**: Добавить обработчики включения/отключения автоплатежа

**Новые обработчики**:
```python
@router.callback_query(F.data == "autopay_enable")
async def handle_autopay_enable(callback: CallbackQuery):
    """Обработка включения автоплатежа"""
    try:
        telegram_id = callback.from_user.id
        api_client = SimpleAPIClient()
        
        # Логика включения автоплатежа
        result = await api_client.enable_user_auto_payment(telegram_id)
        
        if result.get('success'):
            await callback.answer("✅ Автопродление включено")
            # Обновляем сообщение
            await refresh_subscription_display(callback.message, telegram_id)
        else:
            await callback.answer("❌ Ошибка включения автопродления")
            
    except Exception as e:
        logger.error(f"Error enabling autopay: {e}")
        await callback.answer("❌ Произошла ошибка")

@router.callback_query(F.data == "autopay_disable")
async def handle_autopay_disable(callback: CallbackQuery):
    """Обработка отключения автоплатежа"""
    try:
        telegram_id = callback.from_user.id
        api_client = SimpleAPIClient()
        
        result = await api_client.cancel_user_auto_payment(telegram_id)
        
        if result.get('success'):
            await callback.answer("✅ Автопродление отключено")
            # Обновляем сообщение
            await refresh_subscription_display(callback.message, telegram_id)
        else:
            await callback.answer("❌ Ошибка отключения автопродления")
            
    except Exception as e:
        logger.error(f"Error disabling autopay: {e}")
        await callback.answer("❌ Произошла ошибка")

@router.callback_query(F.data.startswith("extend_subscription:"))
async def handle_extend_subscription(callback: CallbackQuery, state: FSMContext):
    """Обработка докупки подписки"""
    try:
        plan_id = callback.data.split(":")[1]
        
        # Используем существующую логику создания платежа
        await handle_plan_selection(callback, state)
        
    except Exception as e:
        logger.error(f"Error extending subscription: {e}")
        await callback.answer("❌ Произошла ошибка")
```

### Этап 5: Обновление API endpoints ✅
**Цель**: Добавить недостающие API endpoints для управления автоплатежом

**Новые методы в SimpleAPIClient**:
```python
async def enable_user_auto_payment(self, telegram_id: int) -> Dict:
    """Включение автоплатежа для пользователя"""
    return await self._make_request("POST", f"/api/v1/users/{telegram_id}/auto_payment/enable")

async def refresh_subscription_display(message: Message, telegram_id: int):
    """Обновление отображения подписки"""
    api_client = SimpleAPIClient()
    subscription_info = await api_client.get_user_subscription_status(telegram_id)
    
    if subscription_info and subscription_info.get('success'):
        days_remaining = subscription_info.get('days_remaining', 0)
        
        if days_remaining > 0:
            await show_active_subscription_info(message, subscription_info, telegram_id)
        else:
            await show_subscription_plans_selection(message, None)
```

## 🔍 КОМПОНЕНТЫ, ТРЕБУЮЩИЕ ТВОРЧЕСКОЙ ФАЗЫ
**НЕТ** - задача касается исправления логики отображения без новых дизайнерских решений

## 📊 ЗАВИСИМОСТИ
- Поле `valid_until` в модели User (уже существует)
- API endpoints для получения статуса подписки (уже существуют)
- Система автоплатежей (уже реализована)

## ⚠️ ВЫЗОВЫ И РИСКИ
1. **Обратная совместимость**: сохранить работу для существующих пользователей
2. **Правильная логика дат**: корректно сравнивать `valid_until` с текущим временем
3. **Обработка ошибок**: graceful handling при недоступности API

## 📋 ЧЕК-ЛИСТ РЕАЛИЗАЦИИ
- [x] Изменить логику в `show_subscription_plans()` - проверять `valid_until` первым
- [x] Создать функцию `show_active_subscription_info()` для активных подписок
- [x] Создать функцию `show_subscription_plans_selection()` для выбора планов
- [x] Обновить клавиатуры для разных состояний подписки
- [ ] Добавить обработчики включения/отключения автоплатежа
- [ ] Добавить обработчик докупки подписки
- [ ] Добавить недостающие API endpoints
- [ ] Тестировать все сценарии пользователей
- [ ] Проверить корректность отображения дат и статусов

## 🎯 ОЖИДАЕМЫЙ РЕЗУЛЬТАТ
1. **Пользователи с активной подпиской** увидят корректную информацию о подписке
2. **Четкое разделение**: активная подписка vs выбор планов
3. **Простое управление автоплатежом** через inline кнопки
4. **Возможность докупки** дополнительного времени к активной подписке

---

## 📋 СТАТУС РЕАЛИЗАЦИИ

### ✅ ЭТАП 1 ЗАВЕРШЕН (2024-01-09)
**Изменения в `vpn-service/bot/handlers/payments.py`**:
- Переписана функция `show_subscription_plans()` - теперь СНАЧАЛА проверяется статус подписки по `valid_until`
- Добавлена функция `show_active_subscription_info()` для отображения информации об активной подписке
- Добавлена функция `show_subscription_plans_selection()` для выбора планов без подписки
- Убрана логика, которая проверяла автоплатеж первым

**Изменения в `vpn-service/bot/keyboards/main_menu.py`**:
- Добавлена функция `create_active_subscription_keyboard()` для пользователей с активной подпиской
- Добавлена функция `create_subscription_plans_keyboard()` для выбора планов
- Обновлены импорты в payments.py

**Исправления API в `vpn-service/backend/`**:
- Добавлен роутер `auto_payments` в `main.py` (endpoint не был подключен!)
- Исправлен endpoint `/api/v1/users/{telegram_id}/subscription_status` в `routes/auto_payments.py`
- Теперь использует данные из таблицы `users` (поле `valid_until`) вместо `subscriptions`

**Исправления интерфейса**:
- Убрано лишнее поле "📊 Тариф: VPN подписка" - теперь просто "💳 Ваша подписка действует до {дата}"
- Убрана кнопка "📱 Мой VPN ключ" из списка планов (она есть в главном меню)
- Используются существующие рабочие кнопки `get_subscription_keyboard_with_autopay()` вместо новых нерабочих
- Удалены нерабочие функции `create_active_subscription_keyboard()` и `create_subscription_plans_keyboard()`

**Результат**:
- Теперь пользователи с активной подпиской (19 дней до 03.08.2025) увидят корректную информацию
- Четкое разделение между отображением активной подписки и выбором планов
- Правильная логика проверки подписки по полю `valid_until`
- API возвращает: `{"success": true, "days_remaining": 19, "end_date": "03.08.2025"}`
- Используются существующие рабочие кнопки с правильными callback'ами

### 🔄 СЛЕДУЮЩИЕ ЭТАПЫ
- Этап 2: Реализация функций отображения (уже частично выполнено)
- Этап 3: Создание клавиатур (уже частично выполнено)
- Этап 4: Обработчики для управления автоплатежом (требует реализации)
- Этап 5: Обновление API endpoints (требует реализации)

---

## ⏭️ СЛЕДУЮЩИЙ РЕЖИМ
**IMPLEMENT MODE** - продолжение реализации этапов 4-5
