"""
Главный файл бота - точка входа в приложение
"""

import asyncio
import structlog
from aiogram import Bot, Dispatcher, Router
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

print("DEBUG: Starting imports...")

from config.settings import get_settings
print("DEBUG: Settings imported")

from handlers import (
    start_router,
    vpn_simplified_router
)
print("DEBUG: Base handlers imported")

from handlers.commands import commands_router
print("DEBUG: Commands handler imported")

from handlers.payments import router as payments_router
print("DEBUG: Payments handler imported")

# from services.pg_storage import pg_storage  # Временно отключено

logger = structlog.get_logger(__name__)
print("DEBUG: Logger configured")

async def on_startup(bot: Bot):
    """
    Выполняется при запуске бота
    """
    logger.info("VPN Bot is starting up")
    
    # Инициализация Postgres
    logger.info("Initializing PostgreSQL storage")
    # pg_storage предварительно инициализируется при импорте
    
    # Установка команд бота
    await bot.set_my_commands([
        BotCommand(command="start", description="Запустить бота"),
        BotCommand(command="create_key", description="Мой VPN ключ"),
        BotCommand(command="refresh_key", description="Обновить ключ"),
        BotCommand(command="subscription", description="Подписка"),
        BotCommand(command="download_apps", description="Скачать приложения"),
        BotCommand(command="support", description="Служба поддержки"),
    ])
    
    logger.info("VPN Bot is ready to accept connections")

async def main():
    """
    Основная функция запуска бота
    """
    print("DEBUG: Entered main() function")
    
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    print("DEBUG: Structlog configured")
    
    logger.info("Initializing VPN Bot")
    print("DEBUG: Logger info called")
    
    # Получаем настройки приложения
    settings = get_settings()
    print("DEBUG: Settings obtained")
    
    # Проверяем конфигурацию
    logger.info("Bot configuration validated", 
               TELEGRAM_TOKEN="***" if settings.TELEGRAM_TOKEN else "MISSING")
    print("DEBUG: Configuration validated")
    
    # Инициализируем бота и диспетчер с хранилищем состояний
    bot = Bot(token=settings.TELEGRAM_TOKEN)
    print("DEBUG: Bot created")
    
    dp = Dispatcher(storage=MemoryStorage())
    print("DEBUG: Dispatcher created")
    
    # Регистрируем роутеры (payments_router должен быть первым для корректной обработки кнопок подписки)
    dp.include_router(payments_router)
    print("DEBUG: Payments router included")
    
    dp.include_router(start_router)
    print("DEBUG: Start router included")
    
    dp.include_router(vpn_simplified_router)
    print("DEBUG: VPN simplified router included")
    
    dp.include_router(commands_router)
    print("DEBUG: Commands router included")
    
    # Установка функций для выполнения при старте/остановке
    dp.startup.register(on_startup)
    print("DEBUG: Startup function registered")
    
    # Запускаем бота
    try:
        logger.info("Starting VPN Bot")
        print("DEBUG: About to delete webhook")
        
        await bot.delete_webhook(drop_pending_updates=True)
        print("DEBUG: Webhook deleted, starting polling")
        
        await dp.start_polling(bot)
        print("DEBUG: Polling started")
        
    except Exception as e:
        print(f"DEBUG: Error during bot operation: {e}")
        logger.error("Bot operation failed", error=str(e))
        raise
    finally:
        logger.info("VPN Bot has been stopped")
        await dp.storage.close()
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main()) 