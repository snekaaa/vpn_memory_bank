"""Скрипт для автоматической инициализации базы данных"""
import asyncio
import logging
from sqlalchemy import text, inspect
from config.database import engine, Base
from config.settings import get_settings
from sqlalchemy.ext.asyncio import create_async_engine
import socket, re

# Импортируем все модели чтобы они были зарегистрированы
from models.user import User
from models.vpn_key import VPNKey
from models.subscription import Subscription
from models.vpn_node import VPNNode
from models.payment import Payment
from models.user_node_assignment import UserNodeAssignment
from models.auto_payment import AutoPayment
from models.payment_retry_attempt import PaymentRetryAttempt
from models.user_notification_preferences import UserNotificationPreferences

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Настройка резервного движка для локального запуска, если host 'db' недоступен
settings = get_settings()
db_url = settings.database_url
fallback_engine = None
try:
    # Проверяем доступность хоста из URL
    host_match = re.search(r"@([^:/]+)", db_url)
    if host_match:
        host = host_match.group(1)
        socket.gethostbyname(host)
except Exception:
    # Если хост не разрешается, заменяем на localhost
    fallback_url = re.sub(r"@[^:/]+", "@localhost", db_url)
    fallback_engine = create_async_engine(
        fallback_url,
        echo=settings.debug,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=3600
    )

async def init_database():
    """Инициализация базы данных - создание таблиц только если их нет"""
    try:
        async with engine.begin() as conn:
            # Проверяем, существуют ли таблицы
            inspector = inspect(conn.sync_connection)
            existing_tables = inspector.get_table_names()
            
            if existing_tables:
                logger.info(f"✅ База данных уже инициализирована. Найдено таблиц: {len(existing_tables)}")
                logger.info(f"📋 Существующие таблицы: {', '.join(existing_tables)}")
                return True
            
            logger.info("📂 Создаю таблицы в базе данных...")
            # Создаём только отсутствующие таблицы
            await conn.run_sync(Base.metadata.create_all)
            
        logger.info("✅ База данных инициализирована успешно")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка при инициализации БД: {e}")
        return False

async def force_reset_database():
    """ОСТОРОЖНО! Полный сброс базы данных - удаляет ВСЕ данные"""
    try:
        # Сбрасываем схему public и создаём заново
        async with engine.begin() as conn:
            logger.warning("🚨 ВНИМАНИЕ! Удаляю схему public и все её объекты...")
            await conn.execute(text("DROP SCHEMA public CASCADE"))
            await conn.execute(text("CREATE SCHEMA public"))
            logger.info("📂 Схема public восстановлена, создаю таблицы...")
            # Создаём все таблицы из моделей
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ База данных полностью пересоздана")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка при сбросе БД: {e}")
        return False

async def reset_data_only():
    """Сброс только данных без удаления схемы"""
    logger.info("🧹 Очищаю данные в таблицах...")
    
    try:
        # Используем резервный движок, если он настроен, иначе основной
        use_engine = fallback_engine or engine
        async with use_engine.begin() as conn:
            # Отключаем foreign key constraints для PostgreSQL
            await conn.execute(text("SET session_replication_role = replica"))
            
            # Очищаем таблицы в правильном порядке (от зависимых к независимым)
            tables_to_clear = [
                "vpn_keys",
                "user_node_assignments", 
                "subscriptions",
                "payments",
                "users",
                "vpn_nodes"
            ]
            
            for table in tables_to_clear:
                try:
                    await conn.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE"))
                    logger.info(f"✅ Очищена таблица {table}")
                except Exception as e:
                    logger.warning(f"⚠️ Не удалось очистить {table}: {e}")
            
            # Включаем обратно foreign key constraints
            await conn.execute(text("SET session_replication_role = DEFAULT"))
            
        logger.info("✅ Данные очищены, схема сохранена")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка при очистке данных: {e}")
        return False

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "reset":
            # Режим сброса данных
            asyncio.run(reset_data_only())
        elif sys.argv[1] == "force-reset":
            # Режим полного сброса (ОПАСНО!)
            confirmation = input("🚨 Вы уверены, что хотите удалить ВСЕ данные? Напишите 'YES' для подтверждения: ")
            if confirmation == "YES":
                asyncio.run(force_reset_database())
            else:
                print("❌ Операция отменена")
    else:
        # Режим безопасной инициализации
        asyncio.run(init_database()) 