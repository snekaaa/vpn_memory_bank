# 🛡️ VPN Admin Interface

PostgreSQL Admin Interface для управления VPN сервисом.

## 🚀 Запуск

Админка интегрирована в основное FastAPI приложение:

```bash
cd vpn-service/backend
python app/main.py
```

Админка доступна по адресу: **http://localhost:8000/admin**

## 🔐 Вход в систему

**Учетные данные по умолчанию:**
- **Username**: `admin`
- **Password**: `secure_admin_123`

> ⚠️ **ВАЖНО**: В продакшене измените пароль через переменные окружения:
> ```bash
> export ADMIN_USERNAME="your_admin"
> export ADMIN_PASSWORD="your_secure_password"
> ```

## 📱 Возможности

### 🏠 Dashboard
- Общая статистика пользователей и VPN ключей
- Мониторинг трафика в реальном времени
- Активность за последние 24 часа
- Системные предупреждения

### 👥 Управление пользователями
- **Просмотр**: Список всех пользователей с пагинацией
- **Поиск**: По имени, username, Telegram ID
- **Действия**:
  - Блокировка/разблокировка пользователей
  - Активация/деактивация аккаунтов
  - Просмотр количества VPN ключей

### 🔑 Управление VPN ключами
- **Просмотр**: Список всех VPN ключей
- **Фильтрация**: По статусу (активные, неактивные, истекшие)
- **Статистика**: Трафик download/upload в ГБ
- **Действия**: Деактивация активных ключей

## 🎨 Responsive дизайн

### 🖥️ Desktop
- Полнофункциональные таблицы
- Sidebar навигация
- Массовые операции

### 📱 Mobile
- Карточный интерфейс
- Hamburger меню
- Touch-friendly кнопки

## 🛡️ Безопасность

### 🔐 Аутентификация
- Session-based login (8 часов)
- HttpOnly cookies
- Auto-logout при истечении сессии

### 🛡️ Защита
- CSRF protection
- Security headers
- Authorization checks на всех роутах
- Input validation через Pydantic

## 📊 API Endpoints

### Auth
- `GET /admin/login` - Страница входа
- `POST /admin/login` - Аутентификация
- `POST /admin/logout` - Выход

### Pages
- `GET /admin/` - Redirect на dashboard
- `GET /admin/dashboard` - Главная страница
- `GET /admin/users` - Управление пользователями
- `GET /admin/vpn-keys` - Управление VPN ключами

### API
- `PATCH /admin/api/users/{id}` - Обновление пользователя
- `PATCH /admin/api/vpn-keys/{id}/deactivate` - Деактивация ключа

## 🔧 Техническая архитектура

### 📁 Структура файлов
```
app/
├── admin/                    # Admin модуль
│   ├── __init__.py
│   ├── auth.py              # Session authentication
│   ├── routes.py            # Admin endpoints
│   └── schemas.py           # Pydantic models
├── templates/               # Jinja2 шаблоны
│   ├── base.html           # Базовый шаблон
│   └── admin/              # Admin страницы
│       ├── login.html
│       ├── dashboard.html
│       ├── users.html
│       └── vpn_keys.html
└── main.py                 # FastAPI app с admin routes
```

### 🗄️ База данных
Использует существующие PostgreSQL модели:
- `User` - информация о пользователях
- `VPNKey` - VPN ключи и статистика

### 🎨 Frontend
- **Bootstrap 5** - CSS framework
- **Bootstrap Icons** - иконки
- **Vanilla JavaScript** - интерактивность
- **Responsive design** - Mobile-first подход

## 🚀 Production готовность

### ✅ Готово к продакшену:
- Интеграция с существующим Docker контейнером
- Работа с PostgreSQL из коробки
- Secure session management
- Responsive UI для всех устройств
- AJAX операции с error handling

### 🔧 Рекомендации для продакшена:
1. **Смените пароль админа** через env переменные
2. **Включите HTTPS** (secure cookies)
3. **Настройте Redis** для session storage (опционально)
4. **Добавьте rate limiting** (опционально)

## 📖 Примеры использования

### Блокировка пользователя
1. Перейти в `/admin/users`
2. Найти пользователя через поиск
3. Нажать кнопку "Заблокировать"
4. Подтвердить действие

### Деактивация VPN ключа
1. Перейти в `/admin/vpn-keys`
2. Отфильтровать активные ключи
3. Нажать кнопку деактивации
4. Подтвердить действие

### Мониторинг статистики
1. Dashboard обновляется автоматически каждые 5 минут
2. Просмотр активности за 24 часа
3. Отслеживание трафика в ГБ

---

**Админка готова к использованию!** 🎉

Вопросы? Проблемы? Проверьте логи FastAPI приложения. 