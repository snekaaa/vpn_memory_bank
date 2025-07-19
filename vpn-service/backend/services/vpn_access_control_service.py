"""
VPN Access Control Service
Централизованная проверка доступа к VPN функциям на основе статуса подписки
"""

import structlog
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.user import User
import aiohttp

logger = structlog.get_logger(__name__)

class VPNAccessControlService:
    """Сервис контроля доступа к VPN функциям"""
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
    
    async def check_vpn_access(self, telegram_id: int) -> Dict[str, Any]:
        """
        Проверка доступа пользователя к VPN функциям
        
        Args:
            telegram_id: Telegram ID пользователя
            
        Returns:
            Dict с информацией о доступе:
            {
                "has_access": bool,
                "reason": str,
                "message": str,
                "days_remaining": int,
                "valid_until": str (ISO format),
                "user_id": int
            }
        """
        try:
            logger.info("🔍 Checking VPN access for user", telegram_id=telegram_id)
            
            # Получаем пользователя по telegram_id
            user = await self._get_user_by_telegram_id(telegram_id)
            
            if not user:
                logger.warning("❌ User not found", telegram_id=telegram_id)
                return {
                    "has_access": False,
                    "reason": "user_not_found",
                    "message": "Пользователь не найден в системе",
                    "days_remaining": 0,
                    "valid_until": None,
                    "user_id": None
                }
            
            # Проверяем активную подписку
            if not user.has_active_subscription:
                days_remaining = user.subscription_days_remaining if hasattr(user, 'subscription_days_remaining') else 0
                
                logger.info("❌ No active subscription", 
                           telegram_id=telegram_id,
                           user_id=user.id,
                           days_remaining=days_remaining,
                           valid_until=user.valid_until)
                
                return {
                    "has_access": False,
                    "reason": "no_subscription", 
                    "message": "Для использования VPN необходима активная подписка",
                    "days_remaining": days_remaining,
                    "valid_until": user.valid_until.isoformat() if user.valid_until else None,
                    "user_id": user.id
                }
            
            # Пользователь имеет активную подписку
            days_remaining = user.subscription_days_remaining if hasattr(user, 'subscription_days_remaining') else 0
            
            logger.info("✅ VPN access granted", 
                       telegram_id=telegram_id,
                       user_id=user.id,
                       days_remaining=days_remaining,
                       valid_until=user.valid_until)
            
            return {
                "has_access": True,
                "reason": "active_subscription",
                "message": f"VPN доступ активен. Осталось: {days_remaining} дн.",
                "days_remaining": days_remaining,
                "valid_until": user.valid_until.isoformat() if user.valid_until else None,
                "user_id": user.id
            }
            
        except Exception as e:
            logger.error("💥 Error checking VPN access", 
                        telegram_id=telegram_id,
                        error=str(e))
            return {
                "has_access": False,
                "reason": "system_error",
                "message": "Ошибка проверки доступа к VPN",
                "days_remaining": 0,
                "valid_until": None,
                "user_id": None
            }
    
    async def get_subscription_plans_for_user(self, telegram_id: int) -> Dict[str, Any]:
        """
        Получить планы подписки для пользователя без доступа к VPN
        
        Args:
            telegram_id: Telegram ID пользователя
            
        Returns:
            Dict с планами подписки и сообщением
        """
        try:
            logger.info("📋 Getting subscription plans for user", telegram_id=telegram_id)
            
            # Получаем планы через прямой API запрос
            plans = await self._get_plans_from_api()
            
            if not plans:
                logger.warning("⚠️ No subscription plans available")
                return {
                    "success": False,
                    "message": "Планы подписки временно недоступны",
                    "plans": {}
                }
            
            # Формируем сообщение для пользователя
            message = (
                "🔐 **Для получения VPN ключа необходима активная подписка**\n\n"
                "📊 Выберите подходящий план:"
            )
            
            logger.info("✅ Subscription plans retrieved", 
                       telegram_id=telegram_id,
                       plans_count=len(plans))
            
            return {
                "success": True,
                "message": message,
                "plans": plans,
                "show_autopay_default": True  # По умолчанию показываем с автоплатежом
            }
            
        except Exception as e:
            logger.error("💥 Error getting subscription plans", 
                        telegram_id=telegram_id,
                        error=str(e))
            return {
                "success": False,
                "message": "Ошибка загрузки планов подписки",
                "plans": {}
            }
    
    async def _get_plans_from_api(self) -> Dict[str, Any]:
        """Получить планы подписки через прямой API запрос"""
        try:
            # Для тестирования создаем простые планы
            # В реальной системе это должен быть запрос к API планов
            mock_plans = {
                "month": {
                    "name": "1 месяц",
                    "price": 199,
                    "discount": None,
                    "period": "1 month"
                },
                "3month": {
                    "name": "3 месяца", 
                    "price": 497,
                    "discount": 16,
                    "period": "3 months"
                },
                "year": {
                    "name": "1 год",
                    "price": 1590,
                    "discount": 33,
                    "period": "12 months"
                }
            }
            
            logger.info("✅ Plans retrieved from mock data", plans_count=len(mock_plans))
            return mock_plans
            
        except Exception as e:
            logger.error("Error getting plans from API", error=str(e))
            return {}
    
    async def check_user_subscription_details(self, telegram_id: int) -> Dict[str, Any]:
        """
        Получить детальную информацию о подписке пользователя
        
        Returns:
            Dict с детальной информацией о подписке
        """
        try:
            user = await self._get_user_by_telegram_id(telegram_id)
            
            if not user:
                return {
                    "found": False,
                    "message": "Пользователь не найден"
                }
            
            now = datetime.now(timezone.utc)
            
            return {
                "found": True,
                "user_id": user.id,
                "telegram_id": telegram_id,
                "subscription_status": user.subscription_status.value if user.subscription_status else "none",
                "valid_until": user.valid_until.isoformat() if user.valid_until else None,
                "valid_until_formatted": user.valid_until.strftime('%d.%m.%Y %H:%M') if user.valid_until else "Не определена",
                "has_active_subscription": user.has_active_subscription,
                "days_remaining": user.subscription_days_remaining if hasattr(user, 'subscription_days_remaining') else 0,
                "is_expired": user.valid_until < now if user.valid_until else True,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "autopay_enabled": getattr(user, 'autopay_enabled', False)
            }
            
        except Exception as e:
            logger.error("Error getting user subscription details", 
                        telegram_id=telegram_id,
                        error=str(e))
            return {
                "found": False,
                "message": f"Ошибка получения данных: {str(e)}"
            }
    
    async def _get_user_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """Получить пользователя по telegram_id"""
        try:
            result = await self.db.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalar_one_or_none()
            
            if user:
                logger.debug("✅ User found", 
                           telegram_id=telegram_id,
                           user_id=user.id,
                           subscription_status=user.subscription_status)
            else:
                logger.debug("❌ User not found", telegram_id=telegram_id)
            
            return user
            
        except Exception as e:
            logger.error("Error fetching user by telegram_id", 
                        telegram_id=telegram_id,
                        error=str(e))
            return None

# Функция-хелпер для использования в других частях системы
async def check_user_vpn_access(db_session: AsyncSession, telegram_id: int) -> Dict[str, Any]:
    """
    Быстрая проверка VPN доступа (функция-хелпер)
    
    Args:
        db_session: Сессия базы данных
        telegram_id: Telegram ID пользователя
        
    Returns:
        Dict с результатом проверки доступа
    """
    service = VPNAccessControlService(db_session)
    return await service.check_vpn_access(telegram_id) 