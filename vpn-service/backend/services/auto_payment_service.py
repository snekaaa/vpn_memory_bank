"""
Сервис для управления автоплатежами
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from models.auto_payment import AutoPayment, AutoPaymentStatus
from models.payment import Payment, PaymentStatus, RecurringStatus
from models.subscription import Subscription, SubscriptionType, SubscriptionStatus
from models.user import User
from services.robokassa_service import RobokassaService
from services.subscription_service import SubscriptionService

logger = logging.getLogger(__name__)

class AutoPaymentService:
    """Сервис для работы с автоплатежами"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def setup_auto_payment(
        self,
        user_id: int,
        payment_id: int,
        previous_invoice_id: str
    ) -> Dict[str, Any]:
        """
        Настройка автоплатежа после первого успешного платежа
        
        Args:
            user_id: ID пользователя
            payment_id: ID платежа
            previous_invoice_id: ID первого успешного платежа в Robokassa
            
        Returns:
            Результат настройки автоплатежа
        """
        try:
            # Получаем данные платежа и подписки
            payment = await self._get_payment(payment_id)
            if not payment:
                return {
                    'success': False,
                    'message': 'Платеж не найден'
                }
                
            subscription = await self._get_user_subscription(user_id)
            if not subscription:
                return {
                    'success': False,
                    'message': 'Подписка не найдена'
                }
            # Получаем SubscriptionService и инициализируем RobokassaService
            subscription_service = SubscriptionService(self.db)
            robokassa_service = await subscription_service._get_robokassa_service()
            
            recurring_result = await robokassa_service.create_recurring_subscription(
                previous_invoice_id=previous_invoice_id,
                amount=float(subscription.price),
                period_days=self._get_period_days(subscription.subscription_type),
                description=f"Автопродление подписки {subscription.plan_name}"
            )
            
            if recurring_result['success']:
                # Сохраняем автоплатеж в БД
                auto_payment = AutoPayment(
                    user_id=user_id,
                    subscription_id=subscription.id,
                    payment_id=payment_id,
                    robokassa_recurring_id=recurring_result['recurring_id'],
                    amount=subscription.price,
                    currency='RUB',
                    period_days=self._get_period_days(subscription.subscription_type),
                    next_payment_date=self._calculate_next_payment_date(subscription),
                    status=AutoPaymentStatus.ACTIVE
                )
                
                self.db.add(auto_payment)
                
                # Обновляем подписку
                subscription.auto_payment_enabled = True
                subscription.robokassa_recurring_id = recurring_result['recurring_id']
                subscription.recurring_setup_payment_id = payment_id
                subscription.next_billing_date = auto_payment.next_payment_date
                subscription.auto_payment_amount = subscription.price
                subscription.auto_payment_status = 'active'
                
                # Обновляем платеж
                payment.recurring_status = RecurringStatus.ACTIVE
                payment.robokassa_recurring_id = recurring_result['recurring_id']
                
                self.db.commit()
                
                logger.info(f"✅ Автоплатеж настроен для пользователя {user_id}, recurring_id: {recurring_result['recurring_id']}")
                
                return {
                    'success': True,
                    'auto_payment_id': auto_payment.id,
                    'recurring_id': recurring_result['recurring_id']
                }
            else:
                logger.error(f"❌ Ошибка настройки автоплатежа в Robokassa: {recurring_result.get('error')}")
                return {
                    'success': False,
                    'message': f"Ошибка настройки автоплатежа: {recurring_result.get('error')}"
                }
                
        except Exception as e:
            logger.error(f"Ошибка настройки автоплатежа: {e}")
            self.db.rollback()
            return {
                'success': False,
                'message': str(e)
            }
    
    async def cancel_auto_payment(self, user_id: int) -> Dict[str, Any]:
        """
        Отмена автоплатежа пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Результат отмены
        """
        try:
            # Находим пользователя
            result = await self.db.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                return {
                    'success': False,
                    'message': 'Пользователь не найден'
                }
            
            # Отключаем настройку автоплатежа
            user.autopay_enabled = False
            await self.db.commit()
            
            logger.info(f"✅ Автоплатеж отключен для пользователя {user_id}")
            
            return {
                'success': True,
                'message': 'Автоплатеж отключен'
            }
                
        except Exception as e:
            logger.error(f"Ошибка отключения автоплатежа: {e}")
            await self.db.rollback()
            return {
                'success': False,
                'message': 'Ошибка отключения автоплатежа'
            }
    
    async def enable_auto_payment(self, user_id: int) -> Dict[str, Any]:
        """
        Включение автоплатежа пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Результат включения
        """
        try:
            # Находим пользователя
            result = await self.db.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                return {
                    'success': False,
                    'message': 'Пользователь не найден'
                }
            
            # Сохраняем настройку автоплатежа
            user.autopay_enabled = True
            await self.db.commit()
            
            logger.info(f"✅ Автоплатеж включен для пользователя {user_id}")
            
            return {
                'success': True,
                'message': 'Автоплатеж включен'
            }
                
        except Exception as e:
            logger.error(f"Ошибка включения автоплатежа: {e}")
            await self.db.rollback()
            return {
                'success': False,
                'message': 'Ошибка включения автоплатежа'
            }

    async def get_user_auto_payment_info(self, user_id: int) -> Dict[str, Any]:
        """
        Получение информации об автоплатеже пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Информация об автоплатеже
        """
        try:
            # Находим пользователя
            result = await self.db.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                return {'enabled': False, 'message': 'Пользователь не найден'}
            
            return {
                'enabled': user.autopay_enabled,
                'message': 'Включен' if user.autopay_enabled else 'Отключен'
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения информации об автоплатеже: {e}")
            return {'enabled': False, 'message': 'Ошибка получения информации'}
    
    async def _get_payment(self, payment_id: int) -> Optional[Payment]:
        """Получение платежа по ID"""
        result = await self.db.execute(
            select(Payment).where(Payment.id == payment_id)
        )
        return result.scalar_one_or_none()
    
    async def _get_user_subscription(self, user_id: int) -> Optional[Subscription]:
        """Получение активной подписки пользователя"""
        result = await self.db.execute(
            select(Subscription).where(
                and_(
                    Subscription.user_id == user_id,
                    Subscription.status == SubscriptionStatus.ACTIVE
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def _get_active_auto_payment(self, user_id: int) -> Optional[AutoPayment]:
        """Получение активного автоплатежа пользователя"""
        result = await self.db.execute(
            select(AutoPayment).where(
                and_(
                    AutoPayment.user_id == user_id,
                    AutoPayment.status == AutoPaymentStatus.ACTIVE
                )
            )
        )
        return result.scalar_one_or_none()
    
    def _get_period_days(self, subscription_type: SubscriptionType) -> int:
        """Получение периода в днях для типа подписки"""
        periods = {
            SubscriptionType.MONTHLY: 30,
            SubscriptionType.QUARTERLY: 90,
            SubscriptionType.SEMI_ANNUAL: 180,
            SubscriptionType.YEARLY: 365
        }
        return periods.get(subscription_type, 30)
    
    def _calculate_next_payment_date(self, subscription: Subscription) -> datetime:
        """Расчет даты следующего платежа"""
        # Следующий платеж за день до окончания подписки
        return subscription.end_date - timedelta(days=1) 