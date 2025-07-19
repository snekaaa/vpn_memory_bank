"""
Subscription Expiry Handler
Автоматическая деактивация VPN ключей при истечении подписки
Запускается по cron расписанию
"""

import asyncio
import structlog
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from config.database import get_db
from models.user import User
from services.vpn_key_lifecycle_service import VPNKeyLifecycleService

logger = structlog.get_logger(__name__)

async def get_users_with_expired_subscriptions(db: AsyncSession) -> List[User]:
    """
    Получить пользователей с истекшей подпиской
    
    Args:
        db: Сессия базы данных
        
    Returns:
        List[User]: Список пользователей с истекшей подпиской
    """
    try:
        now = datetime.now(timezone.utc)
        
        # Ищем пользователей с истекшей подпиской
        result = await db.execute(
            select(User).where(
                User.valid_until.isnot(None),  # Есть подписка
                User.valid_until < now,  # Подписка истекла
                User.is_active == True  # Пользователь активен
            )
        )
        
        expired_users = result.scalars().all()
        
        logger.info("Found users with expired subscriptions", 
                   count=len(expired_users),
                   timestamp=now.isoformat())
        
        return expired_users
        
    except Exception as e:
        logger.error("Error getting users with expired subscriptions", 
                    error=str(e))
        return []

async def handle_expired_subscriptions():
    """Обработка истекших подписок"""
    logger.info("🔄 Starting subscription expiry handling process")
    
    total_processed = 0
    total_deactivated_keys = 0
    errors = []
    
    try:
        # Получаем сессию БД
        async for db in get_db():
            try:
                # 1. Находим пользователей с истекшей подпиской
                expired_users = await get_users_with_expired_subscriptions(db)
                
                if not expired_users:
                    logger.info("📭 No users with expired subscriptions found")
                    return {
                        "success": True,
                        "message": "No expired subscriptions to process",
                        "processed_users": 0,
                        "deactivated_keys": 0
                    }
                
                # 2. Обрабатываем каждого пользователя
                lifecycle_service = VPNKeyLifecycleService(db)
                
                for user in expired_users:
                    try:
                        logger.info("🔒 Processing expired user", 
                                   user_id=user.id,
                                   telegram_id=user.telegram_id,
                                   expired_at=user.valid_until.isoformat() if user.valid_until else None)
                        
                        # Деактивируем VPN ключи
                        result = await lifecycle_service.deactivate_user_keys(user.id)
                        
                        if result.get("success"):
                            deactivated_count = result.get("deactivated_count", 0)
                            total_deactivated_keys += deactivated_count
                            
                            logger.info("✅ Successfully processed expired user", 
                                       user_id=user.id,
                                       deactivated_keys=deactivated_count)
                        else:
                            error_msg = f"Failed to deactivate keys for user {user.id}: {result.get('error', 'Unknown error')}"
                            errors.append(error_msg)
                            logger.error("❌ Failed to process expired user", 
                                       user_id=user.id,
                                       error=result.get('error'))
                        
                        total_processed += 1
                        
                    except Exception as e:
                        error_msg = f"Error processing expired user {user.id}: {str(e)}"
                        errors.append(error_msg)
                        logger.error("💥 Exception processing expired user", 
                                   user_id=user.id,
                                   error=str(e))
                
                # 3. Коммитим все изменения
                await db.commit()
                
                # 4. Формируем итоговый результат
                result = {
                    "success": True,
                    "message": f"Processed {total_processed} expired users, deactivated {total_deactivated_keys} keys",
                    "processed_users": total_processed,
                    "deactivated_keys": total_deactivated_keys,
                    "errors": errors
                }
                
                logger.info("🔒 Subscription expiry handling completed", 
                           result=result)
                
                return result
                
            except Exception as e:
                await db.rollback()
                raise e
            finally:
                await db.close()
                
    except Exception as e:
        error_msg = f"Critical error in subscription expiry handling: {str(e)}"
        logger.error("💥 Critical error in expiry handling", error=str(e))
        
        return {
            "success": False,
            "error": error_msg,
            "processed_users": total_processed,
            "deactivated_keys": total_deactivated_keys
        }

async def main():
    """Точка входа для запуска скрипта"""
    logger.info("🚀 Starting Subscription Expiry Handler")
    
    result = await handle_expired_subscriptions()
    
    if result.get("success"):
        logger.info("✅ Subscription expiry handling completed successfully", 
                   summary=result)
    else:
        logger.error("❌ Subscription expiry handling failed", 
                    error=result.get("error"))
        exit(1)

if __name__ == "__main__":
    """
    Запуск скрипта для обработки истекших подписок
    
    Для добавления в crontab:
    # Каждые 6 часов
    0 */6 * * * cd /path/to/project && python -m scripts.subscription_expiry_handler
    
    # Каждый день в 02:00
    0 2 * * * cd /path/to/project && python -m scripts.subscription_expiry_handler
    """
    
    asyncio.run(main()) 