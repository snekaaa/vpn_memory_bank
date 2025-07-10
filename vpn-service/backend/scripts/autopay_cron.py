#!/usr/bin/env python3
"""
Cron скрипт для обработки автоплатежей
Запускать каждый час через cron:
0 * * * * /path/to/python /path/to/autopay_cron.py >> /var/log/autopay.log 2>&1
"""

import asyncio
import sys
import os
from datetime import datetime

# Добавляем корневую директорию проекта в PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from config.settings import get_settings
from services.payment_scheduler_service import PaymentSchedulerService
import structlog

# Настройка логирования
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.dev.ConsoleRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


async def main():
    """Основная функция обработки автоплатежей"""
    
    start_time = datetime.now()
    logger.info(f"🚀 Запуск обработки автоплатежей: {start_time}")
    
    try:
        # Получаем настройки
        settings = get_settings()
        
        # Создаем подключение к БД
        engine = create_async_engine(
            settings.database_url,
            echo=False,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10
        )
        
        # Создаем сессию
        async_session = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
        
        async with async_session() as db:
            # Создаем и запускаем планировщик
            scheduler = PaymentSchedulerService(db)
            await scheduler.process_due_autopayments()
            
            # Фиксируем изменения
            await db.commit()
        
        # Закрываем движок
        await engine.dispose()
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info(f"✅ Обработка автоплатежей завершена за {duration:.2f} секунд")
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка при обработке автоплатежей: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main()) 