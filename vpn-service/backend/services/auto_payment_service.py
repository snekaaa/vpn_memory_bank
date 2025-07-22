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
                logger.warning(f"User with ID {user_id} not found when disabling auto payment")
                return {
                    'success': False,
                    'message': 'Пользователь не найден',
                    'code': 'user_not_found'
                }
            
            # Проверяем текущий статус подписки (только для логирования)
            has_subscription = user.has_active_subscription
            logger.info(f"Disabling auto payment for user {user_id} with subscription status: {user.subscription_status}, has_active_subscription: {has_subscription}")
            
            # Отключаем настройку автоплатежа независимо от статуса подписки
            user.autopay_enabled = False
            await self.db.commit()
            
            logger.info(f"✅ Автоплатеж отключен для пользователя {user_id}")
            
            return {
                'success': True,
                'message': 'Автоплатеж отключен',
                'autopay_enabled': False,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
                
        except Exception as e:
            logger.error(f"Ошибка отключения автоплатежа для пользователя {user_id}: {e}", exc_info=True)
            await self.db.rollback()
            return {
                'success': False,
                'message': 'Ошибка отключения автоплатежа',
                'error': str(e),
                'code': 'db_error'
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
                logger.warning(f"User with ID {user_id} not found when enabling auto payment")
                return {
                    'success': False,
                    'message': 'Пользователь не найден',
                    'code': 'user_not_found'
                }
            
            # Проверяем текущий статус подписки (только для логирования)
            has_subscription = user.has_active_subscription
            logger.info(f"Enabling auto payment for user {user_id} with subscription status: {user.subscription_status}, has_active_subscription: {has_subscription}")
            
            # Сохраняем настройку автоплатежа независимо от статуса подписки
            user.autopay_enabled = True
            await self.db.commit()
            
            logger.info(f"✅ Автоплатеж включен для пользователя {user_id}")
            
            return {
                'success': True,
                'message': 'Автоплатеж включен',
                'autopay_enabled': True,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
                
        except Exception as e:
            logger.error(f"Ошибка включения автоплатежа для пользователя {user_id}: {e}", exc_info=True)
            await self.db.rollback()
            return {
                'success': False,
                'message': 'Ошибка включения автоплатежа',
                'error': str(e),
                'code': 'db_error'
            }

    async def update_user_auto_payment(self, user_id: int, enabled: bool) -> Dict[str, Any]:
        """
        Обновление настройки автоплатежа пользователя независимо от статуса подписки
        
        Args:
            user_id: ID пользователя
            enabled: Статус автоплатежа (True - включен, False - отключен)
            
        Returns:
            Результат обновления настройки
        """
        try:
            # Находим пользователя
            result = await self.db.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                logger.warning(f"User with ID {user_id} not found when updating auto payment preference")
                return {
                    'success': False,
                    'message': 'Пользователь не найден',
                    'code': 'user_not_found'
                }
            
            # Обновляем настройку автоплатежа независимо от статуса подписки
            previous_value = user.autopay_enabled
            user.autopay_enabled = enabled
            
            # Логируем информацию о статусе подписки для отладки
            subscription_status = user.subscription_status
            has_active_subscription = user.has_active_subscription
            logger.info(
                f"Updating autopay preference for user {user_id}: {previous_value} -> {enabled}, "
                f"subscription_status: {subscription_status}, has_active_subscription: {has_active_subscription}"
            )
            
            # Сохраняем изменения
            try:
                await self.db.commit()
                logger.info(f"✅ Настройка автоплатежа успешно обновлена для пользователя {user_id}")
            except Exception as db_error:
                # Детальное логирование ошибок базы данных
                logger.error(f"❌ Ошибка базы данных при обновлении настройки автоплатежа: {db_error}", exc_info=True)
                await self.db.rollback()
                raise  # Пробрасываем ошибку для обработки во внешнем блоке try/except
            
            return {
                'success': True,
                'message': 'Автоплатеж включен' if enabled else 'Автоплатеж отключен',
                'autopay_enabled': enabled,
                'previous_value': previous_value,
                'subscription_status': subscription_status,
                'has_active_subscription': has_active_subscription,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
                
        except Exception as e:
            # Откатываем изменения в случае ошибки
            try:
                await self.db.rollback()
                logger.info("✅ Транзакция успешно отменена после ошибки")
            except Exception as rollback_error:
                logger.error(f"❌ Ошибка при откате транзакции: {rollback_error}", exc_info=True)
            
            logger.error(f"❌ Ошибка обновления настройки автоплатежа для пользователя {user_id}: {e}", exc_info=True)
            return {
                'success': False,
                'message': 'Ошибка обновления настройки автоплатежа',
                'error': str(e),
                'code': 'db_error'
            }
    
    async def get_user_auto_payment_info(self, user_id: int) -> Dict[str, Any]:
        """
        Получение информации об автоплатеже пользователя независимо от статуса подписки
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Информация об автоплатеже с fallback на значение по умолчанию
        """
        # Значение по умолчанию согласно требованиям
        DEFAULT_AUTOPAY_ENABLED = True
        
        try:
            # Находим пользователя
            result = await self.db.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                logger.warning(f"User with ID {user_id} not found when getting auto payment info")
                # Возвращаем значение по умолчанию, если пользователь не найден
                return {
                    'enabled': DEFAULT_AUTOPAY_ENABLED,
                    'message': 'Пользователь не найден, используется значение по умолчанию',
                    'is_default': True,
                    'code': 'user_not_found',
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
            
            # Получаем настройку автоплатежа независимо от статуса подписки
            # Если значение None, используем значение по умолчанию
            autopay_enabled = user.autopay_enabled if user.autopay_enabled is not None else DEFAULT_AUTOPAY_ENABLED
            is_default_value = user.autopay_enabled is None
            
            # Проверяем наличие активной подписки (только для информации)
            has_subscription = user.has_active_subscription
            
            # Улучшенное логирование для отладки
            logger.info(
                f"Auto payment info for user {user_id}: enabled={autopay_enabled}, "
                f"is_default={is_default_value}, has_subscription={has_subscription}, "
                f"subscription_status={user.subscription_status}, "
                f"raw_autopay_value={user.autopay_enabled}"
            )
            
            return {
                'enabled': autopay_enabled,
                'message': 'Включен' if autopay_enabled else 'Отключен',
                'has_subscription': has_subscription,
                'is_default': is_default_value,
                'subscription_status': str(user.subscription_status),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Ошибка получения информации об автоплатеже для пользователя {user_id}: {error_msg}", exc_info=True)
            
            # Возвращаем значение по умолчанию в случае ошибки (как указано в требованиях)
            return {
                'enabled': DEFAULT_AUTOPAY_ENABLED,
                'message': 'Ошибка получения информации, используется значение по умолчанию',
                'error': error_msg,
                'is_default': True,
                'code': 'db_error',
                'has_subscription': False,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
    
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
    
    async def get_user_auto_payment_info_by_telegram_id(self, telegram_id: int) -> Dict[str, Any]:
        """
        Получение информации об автоплатеже пользователя по telegram_id
        
        Args:
            telegram_id: Telegram ID пользователя
            
        Returns:
            Информация об автоплатеже с fallback на значение по умолчанию
        """
        try:
            # Находим пользователя по telegram_id
            result = await self.db.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                logger.warning(f"User with Telegram ID {telegram_id} not found when getting auto payment info")
                # Возвращаем значение по умолчанию, если пользователь не найден
                return {
                    'enabled': True,  # Значение по умолчанию
                    'message': 'Пользователь не найден, используется значение по умолчанию',
                    'is_default': True,
                    'code': 'user_not_found',
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
            
            # Используем существующий метод для получения информации по user_id
            return await self.get_user_auto_payment_info(user.id)
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Ошибка получения информации об автоплатеже для пользователя с Telegram ID {telegram_id}: {error_msg}", exc_info=True)
            
            # Возвращаем значение по умолчанию в случае ошибки
            return {
                'enabled': True,  # Значение по умолчанию
                'message': 'Ошибка получения информации, используется значение по умолчанию',
                'error': error_msg,
                'is_default': True,
                'code': 'db_error',
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
    
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