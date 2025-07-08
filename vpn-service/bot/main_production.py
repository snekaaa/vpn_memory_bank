"""
Главный файл бота для production - диагностическая версия
"""

import asyncio
import structlog
from aiogram import Bot, Dispatcher, Router
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

print("DEBUG: Starting imports...")

from config.settings import get_settings
print("DEBUG: Settings imported")

logger = structlog.get_logger(__name__)
print("DEBUG: Logger configured")

async def on_startup(bot: Bot):
    """
    Выполняется при запуске бота
    """
    logger.info("VPN Bot (PRODUCTION) is starting up")
    print("DEBUG: on_startup called")
    
    # В production используем только HTTP API для общения с backend
    logger.info("Using HTTP API for backend communication")
    print("DEBUG: Backend communication message logged")
    
    # Установка команд бота
    await bot.set_my_commands([
        BotCommand(command="start", description="Запустить бота"),
        BotCommand(command="help", description="Справка по боту"),
    ])
    print("DEBUG: Bot commands set")
    
    logger.info("VPN Bot (PRODUCTION) is ready to accept connections")
    print("DEBUG: Bot ready")

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
    
    logger.info("Initializing VPN Bot (PRODUCTION)")
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
    
    print("DEBUG: About to import handlers...")
    
    try:
        from handlers import start_router
        print("DEBUG: start_router imported")
        dp.include_router(start_router)
        print("DEBUG: start_router included")
    except Exception as e:
        print(f"DEBUG: Error importing start_router: {e}")
        logger.error("Failed to import start_router", error=str(e))
    
    try:
        from handlers import vpn_simplified_router
        print("DEBUG: vpn_simplified_router imported")
        dp.include_router(vpn_simplified_router)
        print("DEBUG: vpn_simplified_router included")
    except Exception as e:
        print(f"DEBUG: Error importing vpn_simplified_router: {e}")
        logger.error("Failed to import vpn_simplified_router", error=str(e))
    
    try:
        from handlers.commands import commands_router
        print("DEBUG: commands_router imported")
        dp.include_router(commands_router)
        print("DEBUG: commands_router included")
    except Exception as e:
        print(f"DEBUG: Error importing commands_router: {e}")
        logger.error("Failed to import commands_router", error=str(e))
    
    try:
        from handlers.payments import router as payments_router
        print("DEBUG: payments_router imported")
        dp.include_router(payments_router)
        print("DEBUG: payments_router included")
    except Exception as e:
        print(f"DEBUG: Error importing payments_router: {e}")
        logger.error("Failed to import payments_router", error=str(e))
    
    print("DEBUG: All handlers processed")
    
    # Установка функций для выполнения при старте/остановке
    dp.startup.register(on_startup)
    print("DEBUG: Startup registered")
    
    # Запускаем бота
    try:
        logger.info("Starting VPN Bot (PRODUCTION)")
        print("DEBUG: About to delete webhook")
        await bot.delete_webhook(drop_pending_updates=True)
        print("DEBUG: Webhook deleted, starting polling")
        await dp.start_polling(bot)
    finally:
        logger.info("VPN Bot (PRODUCTION) has been stopped")
        print("DEBUG: Bot stopped")
        await dp.storage.close()
        await bot.session.close()

if __name__ == "__main__":
    print("DEBUG: Starting asyncio.run(main())")
    asyncio.run(main()) 