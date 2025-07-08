#!/usr/bin/env python3
"""
Тест создания пользователя для диагностики проблемы
"""

import asyncio
import sys
import os
import traceback

# Добавляем путь к модулям
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.integration_service import integration_service
import structlog

# Настройка логирования
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
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

logger = structlog.get_logger(__name__)

async def test_user_creation():
    """Тестирование создания пользователя"""
    try:
        print("🧪 Тестирование создания пользователя...")
        
        telegram_id = 987654321
        user_data = {
            "username": "debug_user",
            "first_name": "Debug User",
            "language_code": "ru"
        }
        
        print(f"📝 Создаю пользователя telegram_id={telegram_id}")
        
        # Тестируем создание пользователя
        result = await integration_service.create_user_with_subscription(
            telegram_id=telegram_id,
            user_data=user_data,
            subscription_type="trial"
        )
        
        print(f"✅ Результат создания пользователя: {result}")
        
        if result["success"]:
            user_id = result["user_id"]
            print(f"🎯 Пользователь создан с ID: {user_id}")
            
            # Тестируем создание подписки
            print("📝 Создаю подписку...")
            subscription_result = await integration_service.create_subscription_with_payment(
                user_id=user_id,
                subscription_type="trial"
            )
            
            print(f"✅ Результат создания подписки: {subscription_result}")
            
            if subscription_result["success"]:
                subscription_id = subscription_result["subscription_id"]
                print(f"🎯 Подписка создана с ID: {subscription_id}")
                
                # Тестируем создание VPN ключа
                print("📝 Создаю VPN ключ...")
                vpn_result = await integration_service.create_vpn_key_full_cycle(
                    user_id=user_id,
                    subscription_id=subscription_id
                )
                
                print(f"✅ Результат создания VPN ключа: {vpn_result}")
            else:
                print(f"❌ Ошибка создания подписки: {subscription_result}")
        else:
            print(f"❌ Ошибка создания пользователя: {result}")
            
    except Exception as e:
        print(f"💥 Исключение при тестировании: {e}")
        print(f"📋 Трейсбек: {traceback.format_exc()}")

if __name__ == "__main__":
    asyncio.run(test_user_creation()) 