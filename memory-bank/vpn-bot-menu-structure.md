# VPN Telegram Bot - Полная схема меню и навигации

## 🗺️ ОБЩАЯ СТРУКТУРА НАВИГАЦИИ

```mermaid
graph TD
    Start["/start<br>🚀 Команда запуска"] --> Auth["Mock авторизация<br>Генерация user_id"]
    Auth --> MainMenu["🏠 ГЛАВНОЕ МЕНЮ<br>8 основных пунктов"]
    
    %% Основные разделы
    MainMenu --> MyVPN["🔐 Мой VPN"]
    MainMenu --> Subs["💳 Подписки"]
    MainMenu --> Stats["📊 Статистика"]
    MainMenu --> Payments["💰 Платежи"]
    MainMenu --> Profile["👤 Профиль"]
    MainMenu --> Support["🆘 Поддержка"]
    MainMenu --> Help["ℹ️ Помощь"]
    MainMenu --> Admin["👨‍💻 Админ"]
    
    %% Мой VPN раздел
    MyVPN --> VPNCheck{"Есть активная<br>подписка?"}
    VPNCheck -->|"Нет"| NoSub["❌ Нет подписки<br>Переход к покупке"]
    VPNCheck -->|"Да"| VPNActions["🔐 VPN ДЕЙСТВИЯ"]
    
    VPNActions --> GetConfig["📱 Получить конфигурацию"]
    VPNActions --> GetQR["📷 QR-код"]
    VPNActions --> RegenKey["🔄 Обновить ключ"]
    VPNActions --> VPNStats["📊 Статистика VPN"]
    
    %% Подписки раздел
    Subs --> SubsMenu["💳 ВЫБОР ТАРИФА"]
    SubsMenu --> Trial["🆓 Пробная (7 дней)"]
    SubsMenu --> Monthly["📅 Месячная (299₽)"]
    SubsMenu --> Quarterly["📅 Квартальная (799₽)"]
    SubsMenu --> Yearly["📅 Годовая (2999₽)"]
    
    %% Способы оплаты
    Monthly --> PayMethods["💳 СПОСОБЫ ОПЛАТЫ"]
    Quarterly --> PayMethods
    Yearly --> PayMethods
    
    PayMethods --> PayCard["💳 Банковская карта"]
    PayMethods --> PaySBP["⚡ СБП"]
    PayMethods --> PayWallet["💼 Кошельки"]
    PayMethods --> PayCrypto["₿ Криптовалюта"]
    
    %% Админ панель
    Admin --> AdminCheck{"Админские<br>права?"}
    AdminCheck -->|"Нет"| AccessDenied["❌ Доступ запрещен"]
    AdminCheck -->|"Да"| AdminPanel["🔧 АДМИН ПАНЕЛЬ"]
    
    AdminPanel --> AdminStats["📊 Статистика системы"]
    AdminPanel --> UserMgmt["👥 Управление пользователями"]
    AdminPanel --> SubMgmt["📋 Управление подписками"]
    AdminPanel --> UserSearch["🔍 Поиск пользователей"]
    AdminPanel --> GiveSub["🎁 Выдача подписки"]
    AdminPanel --> SysInfo["ℹ️ Информация о системе"]
    
    %% Стили
    style Start fill:#4da6ff,stroke:#0066cc,color:white
    style MainMenu fill:#10b981,stroke:#059669,color:white
    style VPNActions fill:#f59e0b,stroke:#d97706,color:white
    style SubsMenu fill:#8b5cf6,stroke:#7c3aed,color:white
    style PayMethods fill:#ef4444,stroke:#dc2626,color:white
    style AdminPanel fill:#6366f1,stroke:#4f46e5,color:white
```

## 🏠 ГЛАВНОЕ МЕНЮ - Детальная структура

### 1. 🔐 Мой VPN
**Handler**: `menu.py:my_vpn_handler`  
**Callback**: `"my_vpn"`

```mermaid
graph TD
    MyVPN["🔐 Мой VPN"] --> CheckSub{"Проверка активной<br>подписки"}
    
    CheckSub -->|"Подписка есть"| CheckKeys{"VPN ключи<br>доступны?"}
    CheckSub -->|"Нет подписки"| NoSubMsg["❌ У вас нет активной подписки<br>Предложение купить"]
    
    CheckKeys -->|"Ключи есть"| ShowVPN["🔐 Показать VPN данные<br>+ VPN Actions меню"]
    CheckKeys -->|"Нет ключей"| VPNError["⚠️ Подписка активна,<br>но ключ недоступен"]
    
    ShowVPN --> VPNActionsMenu["📱 Получить конфигурацию<br>📷 QR-код<br>🔄 Обновить ключ<br>📊 Статистика"]
    
    NoSubMsg --> SubMenu["💳 Подписки"]
    VPNError --> BackBtn["↩️ Назад"]
    
    style CheckSub fill:#fbbf24,stroke:#f59e0b,color:white
    style ShowVPN fill:#10b981,stroke:#059669,color:white
    style NoSubMsg fill:#ef4444,stroke:#dc2626,color:white
```

### 2. 💳 Подписки
**Handler**: `subscriptions.py` (множественные handlers)  
**Callback**: `"subscriptions"`

```mermaid
graph TD
    Subscriptions["💳 Подписки"] --> SubPlans["4 ТАРИФНЫХ ПЛАНА"]
    
    SubPlans --> Trial["🆓 Пробная<br>(7 дней бесплатно)"]
    SubPlans --> Monthly["📅 Месячная<br>(299₽ / месяц)"]
    SubPlans --> Quarterly["📅 Квартальная<br>(799₽ / 3 месяца)"]
    SubPlans --> Yearly["📅 Годовая<br>(2999₽ / год)"]
    
    Trial --> TrialCheck{"Уже была<br>пробная?"}
    TrialCheck -->|"Нет"| CreateTrial["✅ Создать пробную<br>подписку"]
    TrialCheck -->|"Да"| TrialDenied["⚠️ Пробная уже была<br>Выберите платную"]
    
    Monthly --> PaymentFlow["💳 ВЫБОР СПОСОБА ОПЛАТЫ"]
    Quarterly --> PaymentFlow
    Yearly --> PaymentFlow
    
    PaymentFlow --> Card["💳 Банковская карта"]
    PaymentFlow --> SBP["⚡ СБП"]
    PaymentFlow --> Wallet["💼 Кошельки (ЮMoney)"]
    PaymentFlow --> Crypto["₿ Криптовалюта"]
    
    Card --> YooKassa["YooKassa API<br>Обработка платежа"]
    SBP --> YooKassa
    Wallet --> YooKassa
    Crypto --> CoinGate["CoinGate API<br>Крипто платеж"]
    
    CreateTrial --> VPNGeneration["🔑 Генерация VPN ключа<br>+ 3X-UI интеграция"]
    YooKassa --> VPNGeneration
    CoinGate --> VPNGeneration
    
    style Trial fill:#10b981,stroke:#059669,color:white
    style PaymentFlow fill:#8b5cf6,stroke:#7c3aed,color:white
    style VPNGeneration fill:#f59e0b,stroke:#d97706,color:white
```

### 3. 🔐 VPN Действия (VPN Actions Menu)
**Handler**: `vpn_actions.py`

```mermaid
graph TD
    VPNActions["🔐 VPN ДЕЙСТВИЯ"] --> GetConfig["📱 Получить конфигурацию"]
    VPNActions --> GetQR["📷 QR-код"]
    VPNActions --> RegenKey["🔄 Обновить ключ"]
    VPNActions --> VPNStats["📊 Статистика VPN"]
    
    GetConfig --> ConfigFile["📄 Отправка .txt файла<br>+ показ VLESS URL"]
    GetQR --> QRImage["📱 Отправка QR PNG<br>+ инструкция сканирования"]
    RegenKey --> NewKey["🔄 Генерация нового UUID<br>+ деактивация старого"]
    VPNStats --> StatsDisplay["📊 Трафик / Подключения<br>/ Время использования"]
    
    ConfigFile --> BackToActions["↩️ Назад к VPN действиям"]
    QRImage --> BackToActions
    NewKey --> BackToActions
    StatsDisplay --> BackToActions
    
    style GetConfig fill:#3b82f6,stroke:#2563eb,color:white
    style GetQR fill:#8b5cf6,stroke:#7c3aed,color:white
    style RegenKey fill:#f59e0b,stroke:#d97706,color:white
    style VPNStats fill:#10b981,stroke:#059669,color:white
```

### 4. 👨‍💻 Административная панель
**Handler**: `admin/admin_panel.py`, `admin/user_management.py`, `admin/subscription_management.py`

```mermaid
graph TD
    AdminPanel["👨‍💻 АДМИН ПАНЕЛЬ"] --> AdminStats["📊 Статистика системы"]
    AdminPanel --> UserMgmt["👥 Управление пользователями"]
    AdminPanel --> SubMgmt["📋 Управление подписками"]
    AdminPanel --> UserSearch["🔍 Поиск пользователей"]
    AdminPanel --> GiveSub["🎁 Выдача подписки"]
    AdminPanel --> SysInfo["ℹ️ Информация о системе"]
    
    %% Статистика системы
    AdminStats --> StatsData["📈 Общая аналитика:<br>• Пользователи (всего/активных)<br>• Подписки по типам<br>• Доходы (общий/сегодня)<br>• VPN ключи"]
    
    %% Управление пользователями
    UserMgmt --> UsersList["📋 Список пользователей<br>+ пагинация"]
    UserMgmt --> UserDetail["👤 Детали пользователя<br>+ история подписок"]
    UserMgmt --> UserActions["⚙️ Действия:<br>• Заблокировать<br>• Удалить<br>• Изменить данные"]
    
    %% Управление подписками
    SubMgmt --> SubsList["📋 Список подписок<br>+ фильтры"]
    SubMgmt --> SubDetail["📋 Детали подписки<br>+ VPN ключи"]
    SubMgmt --> SubActions["⚙️ Действия:<br>• Продлить<br>• Деактивировать<br>• Изменить тариф"]
    
    %% Поиск пользователей
    UserSearch --> SearchInput["🔍 Ввод запроса:<br>• Telegram ID<br>• Имя пользователя<br>• Username"]
    SearchInput --> SearchResults["📋 Результаты поиска<br>+ быстрые действия"]
    
    %% Выдача подписки
    GiveSub --> GiveInput["👤 Ввод пользователя<br>(Telegram ID)"]
    GiveInput --> GiveSelect["📋 Выбор типа подписки<br>+ срок действия"]
    GiveSelect --> GiveConfirm["✅ Подтверждение выдачи<br>+ создание VPN ключа"]
    
    style AdminPanel fill:#6366f1,stroke:#4f46e5,color:white
    style UserMgmt fill:#8b5cf6,stroke:#7c3aed,color:white
    style SubMgmt fill:#f59e0b,stroke:#d97706,color:white
    style UserSearch fill:#10b981,stroke:#059669,color:white
```

## 📱 ПОЛЬЗОВАТЕЛЬСКИЕ ПУТИ (User Journeys)

### 🆓 Путь нового пользователя (Trial)

```mermaid
sequenceDiagram
    participant U as 👤 Пользователь
    participant B as 🤖 Бот
    participant S as 💾 LocalStorage
    participant X as 🔧 3X-UI
    
    U->>B: /start
    B->>B: Mock авторизация
    B->>U: 🏠 Главное меню
    U->>B: 💳 Подписки
    B->>U: 📋 Выбор тарифа
    U->>B: 🆓 Пробная
    B->>S: Проверка лимита trial
    S->>B: ✅ Можно создать
    B->>S: Создание подписки + VPN ключа
    B->>X: Создание пользователя в 3X-UI
    X->>B: ✅ Пользователь создан
    B->>U: 🎉 Trial активирован + VLESS ключ
```

### 💳 Путь покупки платной подписки

```mermaid
sequenceDiagram
    participant U as 👤 Пользователь
    participant B as 🤖 Бот
    participant S as 💾 LocalStorage
    participant Y as 💳 YooKassa
    participant X as 🔧 3X-UI
    
    U->>B: 💳 Подписки → 📅 Месячная
    B->>U: 💳 Выбор способа оплаты
    U->>B: 💳 Банковская карта
    B->>Y: Создание платежа
    Y->>U: 🔗 Ссылка на оплату
    U->>Y: 💰 Оплата
    Y->>B: ✅ Платеж успешен
    B->>S: Создание подписки + VPN ключа
    B->>X: Создание пользователя в 3X-UI
    B->>U: 🎉 Подписка активирована + VLESS ключ
```

### 🔐 Путь использования VPN

```mermaid
sequenceDiagram
    participant U as 👤 Пользователь
    participant B as 🤖 Бот
    participant S as 💾 LocalStorage
    
    U->>B: 🔐 Мой VPN
    B->>S: Проверка активной подписки
    S->>B: ✅ Подписка активна
    B->>S: Получение VPN ключей
    S->>B: 🔑 VPN ключ найден
    B->>U: 🔐 VPN меню с данными
    U->>B: 📱 Получить конфигурацию
    B->>U: 📄 .txt файл + VLESS URL
    
    Note over U,B: Альтернативно:
    U->>B: 📷 QR-код
    B->>U: 📱 PNG QR-код + инструкция
```

## 🔧 ТЕХНИЧЕСКИЕ ДЕТАЛИ

### FSM States (Конечный автомат состояний)

```python
# AdminStates (admin/admin_panel.py)
class AdminStates(StatesGroup):
    waiting_for_search = State()      # Ожидание поискового запроса
    waiting_for_user_id = State()     # Ожидание ID пользователя
    users_menu = State()              # Меню пользователей
    users_list = State()              # Список пользователей
    user_detail = State()             # Детали пользователя
    subscriptions_menu = State()      # Меню подписок
    subscriptions_list = State()      # Список подписок
    subscription_detail = State()     # Детали подписки
    subscription_create = State()     # Создание подписки
```

### Callback Data Mapping

```python
# Основные callback'и главного меню
MAIN_MENU_CALLBACKS = {
    "my_vpn": "🔐 Мой VPN",
    "subscriptions": "💳 Подписки", 
    "statistics": "📊 Статистика",
    "payments": "💰 Платежи",
    "profile": "👤 Профиль",
    "support": "🆘 Поддержка",
    "help": "ℹ️ Помощь",
    "admin_panel": "👨‍💻 Админ"
}

# Подписки
SUBSCRIPTION_CALLBACKS = {
    "trial_subscription": "🆓 Пробная",
    "monthly_subscription": "📅 Месячная",
    "quarterly_subscription": "📅 Квартальная", 
    "yearly_subscription": "📅 Годовая"
}

# Способы оплаты
PAYMENT_CALLBACKS = {
    "payment_card": "💳 Банковская карта",
    "payment_sbp": "⚡ СБП", 
    "payment_yoomoney": "💼 ЮMoney",
    "payment_crypto": "₿ Криптовалюта"
}

# VPN действия
VPN_ACTION_CALLBACKS = {
    "get_config": "📱 Получить конфигурацию",
    "get_qr": "📷 QR-код",
    "regenerate_key": "🔄 Обновить ключ",
    "vpn_stats": "📊 Статистика VPN"
}

# Админские действия
ADMIN_CALLBACKS = {
    "admin_stats": "📊 Статистика системы",
    "admin_users": "👥 Управление пользователями",
    "admin_subscriptions": "📋 Управление подписками",
    "admin_user_search": "🔍 Поиск пользователей",
    "admin_give_subscription": "🎁 Выдача подписки",
    "admin_page_info": "ℹ️ Информация о системе"
}
```

### Навигационные кнопки

```python
# Системные кнопки возврата
NAVIGATION_CALLBACKS = {
    "back_to_main": "↩️ Главное меню",
    "back_to_subscriptions": "↩️ К подпискам", 
    "back_to_vpn": "↩️ К VPN действиям",
    "admin_back_to_menu": "↩️ Админ меню"
}
```

## 📊 СТАТИСТИКА СТРУКТУРЫ МЕНЮ

### Количественные показатели:
- **Всего пунктов главного меню**: 8
- **Всего callback handlers**: 45+
- **FSM состояний**: 9 (AdminStates)
- **Тарифных планов**: 4
- **Способов оплаты**: 4  
- **VPN действий**: 4
- **Админских функций**: 6
- **Файлов handlers**: 7
- **Keyboard модулей**: 2

### Глубина навигации:
- **Максимальная глубина**: 4 уровня (Главное меню → Подписки → Оплата → Подтверждение)
- **Среднее количество кликов до цели**: 2-3
- **Точек возврата**: 15+ кнопок "↩️ Назад"

## 🎯 РЕЗЮМЕ СТРУКТУРЫ

VPN Telegram бот имеет **хорошо структурированную навигацию** с четким разделением:

1. **Пользовательская часть**: Интуитивное управление подписками и VPN ключами
2. **Административная часть**: Полноценная система управления пользователями и подписками  
3. **Техническая часть**: Mock авторизация + LocalStorage + 3X-UI интеграция
4. **Платежная часть**: 4 способа оплаты через YooKassa и CoinGate

**Архитектура поддерживает**:
- ✅ Scalability (легко добавлять новые функции)
- ✅ Maintainability (четкое разделение по handlers)
- ✅ User Experience (логичная навигация)
- ✅ Admin Capabilities (полное управление системой) 