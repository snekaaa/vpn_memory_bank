# Технологический стек и система сборки

## Стек бэкенда
- **Фреймворк**: FastAPI (Python) с асинхронными паттернами async/await
- **База данных**: PostgreSQL 15 с ORM SQLAlchemy 2.0 (асинхронный)
- **Аутентификация**: Сессионная аутентификация администратора
- **Архитектура API**: RESTful-эндпоинты с документацией OpenAPI
- **Обработка платежей**: Паттерн фабрики для нескольких провайдеров (Robokassa, FreeKassa, YooKassa)

## Стек бота
- **Фреймворк**: aiogram 3.2.0 (Telegram Bot API)
- **Хранилище**: Интеграция с PostgreSQL через асинхронные соединения
- **Интерфейс**: Пользовательские клавиатуры с инлайн-кнопками
- **Платежный процесс**: Интегрированные рабочие процессы обработки платежей

## Инфраструктура
- **Контейнеризация**: Docker + Docker Compose
- **VPN-технология**: Панели X3UI с протоколом VLESS
- **Балансировка нагрузки**: Назначение узлов по принципу round-robin с проверками работоспособности
- **Мониторинг**: Автоматические проверки работоспособности с восстановлением

## Ключевые библиотеки
- **Веб**: FastAPI 0.104.1, uvicorn, gunicorn
- **База данных**: SQLAlchemy 2.0.23, alembic, asyncpg, psycopg2-binary
- **Бот**: aiogram 3.2.0, aiohttp 3.9.1
- **Платежи**: yookassa, requests, httpx
- **Безопасность**: python-jose, passlib с bcrypt
- **Фоновые задачи**: celery, redis
- **Утилиты**: pydantic 2.5.0, structlog, qrcode

## Админка
- **Доступ**: `/admin`
- **Логин**: admin
- **Пароль**: secure_admin_123
- **Функции**: Управление пользователями, подписками, VPN-ключами, платежами и настройками системы

## Основные команды

### Разработка
```bash
# Запуск среды разработки
docker-compose up -d

# Сервер разработки бэкенда
cd vpn-service/backend && uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Разработка бота
cd vpn-service/bot && python main.py

# Миграции базы данных
cd vpn-service/backend && alembic upgrade head
```

### Продакшн
```bash
# Деплой в продакшн
./deploy.sh

# Контейнеры продакшн
docker-compose -f docker-compose.prod.yml up -d --build --force-recreate

# Проверка статуса
docker-compose -f docker-compose.prod.yml ps

# Просмотр логов
docker logs vpn_memory_bank_backend_1 --tail 50
```

### Тестирование
```bash
# Запуск тестов бэкенда
cd vpn-service/backend && pytest

# Тестирование конкретной интеграции
python test_full_vpn_subscription_integration.py

# Тестирование API X3UI
./run_x3ui_tests.sh
```

### База данных
```bash
# Инициализация базы данных
python init_database.py

# Подключение к продакшн БД
docker exec -it vpn_memory_bank_db_1 psql -U vpn_user -d vpn_db

# Резервное копирование базы данных
pg_dump -h localhost -p 5433 -U vpn_user vpn_db > backup.sql
```