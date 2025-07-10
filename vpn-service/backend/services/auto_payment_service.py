"""
Сервис для управления автоплатежами
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import select, and_

from models.auto_payment import AutoPayment, AutoPaymentStatus
from models.payment import Payment, PaymentStatus, RecurringStatus
from models.subscription import Subscription, SubscriptionType
from models.user import User
from services.robokassa_service import RobokassaService
from services.subscription_service import SubscriptionService

logger = logging.getLogger(__name__)

class AutoPaymentService:
    """Сервис для работы с автоплатежами"""
    
    def __init__(self, db: Session):
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
            # Находим активный автоплатеж
            auto_payment = await self._get_active_auto_payment(user_id)
            
            if not auto_payment:
                return {
                    'success': False,
                    'message': 'Активный автоплатеж не найден'
                }
            
            # Получаем SubscriptionService и инициализируем RobokassaService
            subscription_service = SubscriptionService(self.db)
            robokassa_service = await subscription_service._get_robokassa_service()
            cancel_result = await robokassa_service.cancel_recurring_subscription(
                auto_payment.robokassa_recurring_id
            )
            
            if cancel_result['success']:
                # Обновляем статус в БД
                auto_payment.status = AutoPaymentStatus.CANCELLED
                
                # Обновляем подписку
                subscription = self.db.query(Subscription).filter(
                    Subscription.id == auto_payment.subscription_id
                ).first()
                
                if subscription:
                    subscription.auto_payment_enabled = False
                    subscription.auto_payment_status = 'cancelled'
                
                self.db.commit()
                
                logger.info(f"✅ Автоплатеж отменен для пользователя {user_id}")
                
                return {
                    'success': True,
                    'message': 'Автоплатеж отключен'
                }
            else:
                logger.error(f"❌ Ошибка отмены автоплатежа в Robokassa: {cancel_result.get('result')}")
                return {
                    'success': False,
                    'message': 'Ошибка отмены автоплатежа'
                }
                
        except Exception as e:
            logger.error(f"Ошибка отмены автоплатежа: {e}")
            self.db.rollback()
            return {
                'success': False,
                'message': str(e)
            }
    
    async def get_user_auto_payment_info(self, user_id: int) -> Dict[str, Any]:
        """
        Получение информации об автоплатеже пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Информация об автоплатеже
        """
        auto_payment = await self._get_active_auto_payment(user_id)
        
        if auto_payment:
            return {
                'enabled': True,
                'amount': float(auto_payment.amount),
                'currency': auto_payment.currency,
                'next_payment_date': auto_payment.next_payment_date,
                'period_days': auto_payment.period_days,
                'status': auto_payment.status,
                'attempts_count': auto_payment.attempts_count,
                'last_attempt_date': auto_payment.last_attempt_date
            }
        
        return {'enabled': False}
    
    async def _get_payment(self, payment_id: int) -> Optional[Payment]:
        """Получение платежа по ID"""
        return self.db.query(Payment).filter(Payment.id == payment_id).first()
    
    async def _get_user_subscription(self, user_id: int) -> Optional[Subscription]:
        """Получение активной подписки пользователя"""
        return self.db.query(Subscription).filter(
            and_(
                Subscription.user_id == user_id,
                Subscription.status == 'active'
            )
        ).first()
    
    async def _get_active_auto_payment(self, user_id: int) -> Optional[AutoPayment]:
        """Получение активного автоплатежа пользователя"""
        return self.db.query(AutoPayment).filter(
            and_(
                AutoPayment.user_id == user_id,
                AutoPayment.status == AutoPaymentStatus.ACTIVE
            )
        ).first()
    
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