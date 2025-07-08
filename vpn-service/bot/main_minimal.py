#!/usr/bin/env python3
"""
Минимальная версия бота для тестирования
"""

import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message
from aiogram.filters import Command
import os
from dotenv import load_dotenv

load_dotenv()

async def start_handler(message: Message):
    """Обработчик команды /start"""
    await message.answer("🤖 Минимальный бот работает!")

async def main():
    """Основная функция"""
    print("🚀 Starting minimal bot...")
    
    # Получаем токен
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("❌ No Telegram token found!")
        return
        
    print(f"✅ Token found: {token[:20]}...")
    
    # Создаем бота и диспетчер
    bot = Bot(token=token)
    dp = Dispatcher(storage=MemoryStorage())
    
    print("✅ Bot and dispatcher created")
    
    # Регистрируем хендлер
    dp.message.register(start_handler, Command(commands=["start"]))
    
    print("✅ Handlers registered")
    
    try:
        print("🔄 Deleting webhook...")
        await bot.delete_webhook(drop_pending_updates=True)
        
        print("🔄 Starting polling...")
        await dp.start_polling(bot)
        
    except Exception as e:
        print(f"💥 Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("🔄 Closing bot session...")
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main()) 