"""
Сервис для управления подписками пользователей
Реализует активацию, проверку статуса и управление подписками
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, text
from sqlalchemy.orm import selectinload

from models.user import User, UserSubscriptionStatus
from models.subscription import Subscription, SubscriptionStatus, SubscriptionType
from models.payment import Payment, PaymentStatus
from models.payment_provider import PaymentProvider, PaymentProviderType
from services.robokassa_service import RobokassaService

logger = logging.getLogger(__name__)

class SubscriptionService:
    """Сервис для управления подписками"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self._robokassa_service = None
    
    async def _get_robokassa_service(self) -> RobokassaService:
        """Получение сервиса Robokassa с конфигурацией из БД"""
        if self._robokassa_service is None:
            # Получаем активный провайдер Robokassa из БД
            result = await self.db.execute(
                select(PaymentProvider).where(
                    PaymentProvider.provider_type == PaymentProviderType.robokassa,
                    PaymentProvider.is_active == True
                ).order_by(PaymentProvider.priority.asc())
            )
            provider = result.scalar_one_or_none()
            
            if provider:
                # Используем конфигурацию из БД
                provider_config = provider.get_robokassa_config()
                self._robokassa_service = RobokassaService(provider_config=provider_config)
                logger.info("Robokassa service initialized with DB config")
            else:
                # Если провайдер не найден, логируем ошибку
                logger.error("No active Robokassa provider found in database")
                raise Exception("Robokassa провайдер не настроен в системе")
        
        return self._robokassa_service
    
    async def get_user_subscription_status(self, user_id: int) -> Dict[str, Any]:
        """
        Получение статуса подписки пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Словарь с информацией о подписке
        """
        try:
            # Получаем пользователя
            result = await self.db.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                return {
                    'status': 'not_found',
                    'message': 'Пользователь не найден'
                }
            
            # Проверяем актуальность статуса подписки
            await self._update_expired_subscription(user)
            
            return {
                'status': 'success',
                'subscription_status': user.subscription_status.value,
                'subscription_end_date': user.valid_until,
                'has_active_subscription': user.has_active_subscription,
                'days_remaining': user.subscription_days_remaining
            }
            
        except Exception as e:
            logger.error(f"Error getting subscription status for user {user_id}: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    async def activate_subscription(
        self, 
        user_id: int, 
        subscription_type: str, 
        payment_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Активация подписки для пользователя
        
        Args:
            user_id: ID пользователя
            subscription_type: Тип подписки (monthly, quarterly, etc.)
            payment_id: ID платежа (опционально)
            
        Returns:
            Результат активации
        """
        try:
            # Получаем план подписки
            robokassa_service = await self._get_robokassa_service()
            plans = robokassa_service.get_subscription_plans()
            plan = plans.get(subscription_type)
            
            if not plan:
                return {
                    'status': 'error',
                    'message': 'Неверный тип подписки'
                }
            
            # Получаем пользователя
            result = await self.db.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                return {
                    'status': 'error',
                    'message': 'Пользователь не найден'
                }
            
            # Рассчитываем даты подписки
            current_time = datetime.now(timezone.utc)
            
            # Продлеваем подписку пользователя используя метод модели
            user.extend_subscription(plan['duration_days'])
            
            # Получаем конечную дату для записи подписки
            end_date = user.valid_until
            start_date = end_date - timedelta(days=plan['duration_days']) if user.has_active_subscription else current_time
            
            # Создаем запись подписки
            subscription_type_enum = self._get_subscription_type_enum(subscription_type)
            
            subscription = Subscription(
                user_id=user_id,
                subscription_type=subscription_type_enum,
                status=SubscriptionStatus.ACTIVE,
                price=plan['price'],
                currency=plan['currency'],
                start_date=start_date,
                end_date=end_date
            )
            
            self.db.add(subscription)
            
            # Связываем с платежом, если указан
            if payment_id:
                await self.db.execute(
                    update(Payment)
                    .where(Payment.id == payment_id)
                    .values(
                        subscription_id=subscription.id,
                        processed_at=current_time
                    )
                )
            
            await self.db.commit()
            
            logger.info(f"Activated subscription for user {user_id}, type {subscription_type}")
            
            return {
                'status': 'success',
                'message': 'Подписка успешно активирована',
                'subscription_id': subscription.id,
                'end_date': end_date,
                'days_added': plan['duration_days']
            }
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error activating subscription: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    async def check_and_update_expired_subscriptions(self) -> Dict[str, Any]:
        """
        Проверка и обновление истекших подписок
        
        Returns:
            Результат обновления
        """
        try:
            current_time = datetime.now(timezone.utc)
            
            # Находим пользователей с истекшими подписками
            result = await self.db.execute(
                select(User).where(
                    User.subscription_status == 'active',
                    User.subscription_end_date < current_time
                )
            )
            expired_users = result.scalars().all()
            
            updated_count = 0
            for user in expired_users:
                await self.db.execute(
                    update(User)
                    .where(User.id == user.id)
                    .values(
                        subscription_status='expired',
                        updated_at=current_time
                    )
                )
                updated_count += 1
            
            await self.db.commit()
            
            logger.info(f"Updated {updated_count} expired subscriptions")
            
            return {
                'status': 'success',
                'updated_count': updated_count
            }
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error updating expired subscriptions: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    async def get_subscription_plans(self) -> Dict[str, Dict[str, Any]]:
        """
        Получение доступных тарифных планов
        
        Returns:
            Словарь с тарифными планами
        """
        robokassa_service = await self._get_robokassa_service()
        return robokassa_service.get_subscription_plans()
    
    async def get_user_subscriptions_history(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Получение истории подписок пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Список подписок
        """
        try:
            result = await self.db.execute(
                select(Subscription)
                .where(Subscription.user_id == user_id)
                .order_by(Subscription.created_at.desc())
            )
            subscriptions = result.scalars().all()
            
            return [
                {
                    'id': sub.id,
                    'type': sub.subscription_type.value,
                    'status': sub.status.value,
                    'price': float(sub.price),
                    'currency': sub.currency,
                    'start_date': sub.start_date,
                    'end_date': sub.end_date,
                    'created_at': sub.created_at,
                    'is_active': sub.is_active
                }
                for sub in subscriptions
            ]
            
        except Exception as e:
            logger.error(f"Error getting subscriptions history: {e}")
            return []
    
    async def suspend_subscription(self, user_id: int, reason: str = None) -> Dict[str, Any]:
        """
        Приостановка подписки пользователя
        
        Args:
            user_id: ID пользователя
            reason: Причина приостановки
            
        Returns:
            Результат операции
        """
        try:
            current_time = datetime.now(timezone.utc)
            
            # Обновляем статус пользователя
            result = await self.db.execute(
                update(User)
                .where(User.id == user_id)
                .values(
                    subscription_status='suspended',
                    updated_at=current_time
                )
            )
            
            if result.rowcount == 0:
                return {
                    'status': 'error',
                    'message': 'Пользователь не найден'
                }
            
            # Обновляем активные подписки
            await self.db.execute(
                update(Subscription)
                .where(
                    Subscription.user_id == user_id,
                    Subscription.status == SubscriptionStatus.ACTIVE
                )
                .values(
                    status=SubscriptionStatus.SUSPENDED,
                    updated_at=current_time,
                    notes=reason
                )
            )
            
            await self.db.commit()
            
            logger.info(f"Suspended subscription for user {user_id}")
            
            return {
                'status': 'success',
                'message': 'Подписка приостановлена'
            }
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error suspending subscription: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    async def _update_expired_subscription(self, user: User) -> None:
        """
        Обновление статуса подписки если она истекла
        
        Args:
            user: Пользователь
        """
        if (user.subscription_status == 'active' and
            user.subscription_end_date and
            user.subscription_end_date < datetime.now(timezone.utc)):
            
            user.subscription_status = 'expired'
            user.updated_at = datetime.now(timezone.utc)
            await self.db.commit()
    
    def _get_subscription_type_enum(self, subscription_type: str) -> SubscriptionType:
        """
        Преобразование строки в enum SubscriptionType
        
        Args:
            subscription_type: Строковое представление типа
            
        Returns:
            Enum значение
        """
        mapping = {
            'monthly': SubscriptionType.MONTHLY,
            'quarterly': SubscriptionType.QUARTERLY,
            'semi_annual': SubscriptionType.SEMI_ANNUAL,
            'annual': SubscriptionType.YEARLY
        }
        
        return mapping.get(subscription_type, SubscriptionType.MONTHLY) 