"""
Payment Scheduler Service
Обработка автоплатежей по расписанию
"""

import structlog
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.sql import func

from models.auto_payment import AutoPayment
from models.payment import Payment, PaymentStatus, PaymentMethod
from models.payment_retry_attempt import PaymentRetryAttempt
from models.subscription import Subscription
from models.user import User
from services.robokassa_service import RobokassaService
from services.subscription_service import SubscriptionService
from services.notification_service import notification_service

logger = structlog.get_logger(__name__)


class PaymentSchedulerService:
    """Сервис для обработки автоплатежей по расписанию"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def process_due_autopayments(self):
        """Обработка автоплатежей, которые пора выполнить"""
        
        # Находим автоплатежи, которые пора выполнить
        due_autopayments = await self._get_due_autopayments()
        
        logger.info(f"🔄 Найдено {len(due_autopayments)} автоплатежей для обработки")
        
        for autopay in due_autopayments:
            try:
                await self._process_single_autopayment(autopay)
            except Exception as e:
                logger.error(f"❌ Ошибка обработки автоплатежа {autopay.id}: {e}")
    
    async def _get_due_autopayments(self) -> List[AutoPayment]:
        """Получение автоплатежей, которые пора выполнить"""
        
        current_time = datetime.utcnow()
        
        result = await self.db.execute(
            select(AutoPayment)
            .where(
                and_(
                    AutoPayment.status == "active",
                    AutoPayment.next_payment_date <= current_time
                )
            )
        )
        
        return result.scalars().all()
    
    async def _process_single_autopayment(self, autopay: AutoPayment):
        """Обработка одного автоплатежа"""
        
        logger.info(f"💳 Обработка автоплатежа {autopay.id} для пользователя {autopay.user_id}")
        
        # Получаем провайдера Robokassa
        from services.payment_provider_service import get_payment_provider_service
        provider_service = get_payment_provider_service(self.db)
        robokassa_provider = await provider_service.get_default_provider("robokassa")
        
        if not robokassa_provider:
            logger.error("❌ Robokassa провайдер не найден")
            await self._handle_failed_autopayment(autopay, {"error": "Robokassa provider not found"})
            return
        
        # Выполняем списание через Robokassa Recurring API
        robokassa_service = RobokassaService(robokassa_provider.config)
        
        recurring_result = await robokassa_service.create_recurring_subscription_with_logging(
            auto_payment_id=autopay.id,
            previous_invoice_id=autopay.robokassa_recurring_id,
            amount=float(autopay.amount),
            description=f"Автопродление подписки (попытка {autopay.attempts_count + 1})"
        )
        
        if recurring_result['success']:
            # Платеж успешен - продлеваем подписку
            await self._handle_successful_autopayment(autopay)
        else:
            # Платеж неудачен - обрабатываем ошибку
            await self._handle_failed_autopayment(autopay, recurring_result)
    
    async def _handle_successful_autopayment(self, autopay: AutoPayment):
        """Обработка успешного автоплатежа"""
        
        logger.info(f"✅ Автоплатеж {autopay.id} успешно выполнен")
        
        # Создаем запись платежа
        payment = Payment(
            user_id=autopay.user_id,
            subscription_id=autopay.subscription_id,
            amount=autopay.amount,
            currency=autopay.currency,
            status=PaymentStatus.SUCCEEDED,
            payment_method=PaymentMethod.robokassa,
            is_autopay_generated=True,
            autopay_attempt_number=autopay.attempts_count + 1,
            autopay_parent_payment_id=autopay.payment_id,
            robokassa_recurring_id=autopay.robokassa_recurring_id,
            description=f"Автопродление подписки",
            paid_at=datetime.utcnow(),
            processed_at=datetime.utcnow()
        )
        
        self.db.add(payment)
        
        # Продлеваем подписку пользователя
        subscription_service = SubscriptionService(self.db)
        await subscription_service.extend_user_subscription(
            autopay.user_id,
            autopay.period_days
        )
        
        # Обновляем дату следующего платежа
        autopay.next_payment_date = datetime.utcnow() + timedelta(days=autopay.period_days)
        autopay.attempts_count = 0  # Сбрасываем счетчик попыток
        autopay.last_payment_date = datetime.utcnow()
        
        await self.db.commit()
        
        # Отправляем уведомление об успешном продлении
        await notification_service.send_notification(
            user_id=autopay.user_id,
            message=(
                f"✅ Подписка продлена автоматически!\n\n"
                f"💰 Списано: {autopay.amount}₽\n"
                f"📅 Следующее списание: {autopay.next_payment_date.strftime('%d.%m.%Y')}"
            )
        )
        
        # НОВОЕ: Автоматически обновляем меню пользователя после успешного автоплатежа
        try:
            from services.menu_updater_service import menu_updater_service
            # Получаем telegram_id пользователя
            user_query = select(User).where(User.id == autopay.user_id)
            user_result = await self.db.execute(user_query)
            user = user_result.scalar_one_or_none()
            
            if user and user.telegram_id:
                await menu_updater_service.update_user_menu_after_payment(user.telegram_id)
                logger.info("✅ User menu updated after successful autopayment", 
                           telegram_id=user.telegram_id,
                           autopay_id=autopay.id)
        except Exception as menu_error:
            logger.error("❌ Failed to update user menu after autopayment", 
                       autopay_id=autopay.id,
                       error=str(menu_error))
            # Не прерываем основной процесс из-за ошибки обновления меню
    
    async def _handle_failed_autopayment(self, autopay: AutoPayment, error_result: Dict[str, Any]):
        """Обработка неудачного автоплатежа"""
        
        autopay.attempts_count += 1
        autopay.last_attempt_date = datetime.utcnow()
        
        logger.warning(
            f"⚠️ Автоплатеж {autopay.id} не удался (попытка {autopay.attempts_count})",
            error=error_result.get('error')
        )
        
        # Классифицируем ошибку
        error_type = error_result.get('error_type', 'unknown_error')
        
        # Создаем запись о попытке
        retry_attempt = PaymentRetryAttempt(
            auto_payment_id=autopay.id,
            attempt_number=autopay.attempts_count,
            error_type=error_type,
            error_message=error_result.get('error'),
            robokassa_response=error_result.get('raw_response'),
            scheduled_at=autopay.next_payment_date,
            attempted_at=datetime.utcnow(),
            result='failed'
        )
        
        # Определяем следующую попытку
        next_attempt = self._calculate_next_attempt(error_type, autopay.attempts_count)
        
        if next_attempt:
            retry_attempt.next_attempt_at = next_attempt
            autopay.next_payment_date = next_attempt
            
            # Отправляем уведомления в зависимости от попытки
            await self._send_failure_notification(autopay, error_type, autopay.attempts_count)
            
        else:
            # Все попытки исчерпаны
            autopay.status = 'failed'
            await self._handle_max_attempts_reached(autopay)
        
        self.db.add(retry_attempt)
        await self.db.commit()
    
    def _calculate_next_attempt(self, error_type: str, attempt_number: int) -> Optional[datetime]:
        """Вычисление времени следующей попытки"""
        
        retry_intervals = {
            'insufficient_funds': [24, 72, 168],  # 24ч, 72ч, 7 дней
            'technical_error': [1, 6, 24],        # 1ч, 6ч, 24ч  
            'card_issue': [24],                   # 24ч (только одна попытка)
            'unknown_error': [6, 24, 72]          # 6ч, 24ч, 72ч
        }
        
        intervals = retry_intervals.get(error_type, retry_intervals['unknown_error'])
        
        if attempt_number <= len(intervals):
            hours = intervals[attempt_number - 1]
            return datetime.utcnow() + timedelta(hours=hours)
        
        return None
    
    async def _send_failure_notification(self, autopay: AutoPayment, error_type: str, attempt_number: int):
        """Отправка уведомления о неудачной попытке"""
        
        # Получаем пользователя для информации о подписке
        user_result = await self.db.execute(
            select(User).where(User.id == autopay.user_id)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            return
        
        # Вычисляем дней до истечения подписки
        days_remaining = 0
        if user.valid_until:
            delta = user.valid_until - datetime.utcnow()
            days_remaining = max(0, delta.days)
        
        # Формируем сообщение в зависимости от попытки
        if attempt_number == 1:
            message = (
                "⚠️ Не удалось продлить подписку автоматически\n\n"
                f"Причина: {self._get_error_reason_text(error_type)}\n"
                "🔄 Повторная попытка через 24 часа\n\n"
                "💡 Проверьте баланс карты"
            )
        elif attempt_number == 2:
            message = (
                "⚠️ Повторная попытка автоплатежа не удалась\n\n"
                f"Причина: {self._get_error_reason_text(error_type)}\n"
                "🔄 Последняя попытка через 72 часа\n"
                f"⏰ Подписка истекает через {days_remaining} дней\n\n"
                "❗ Рекомендуем обновить способ оплаты"
            )
        else:
            message = (
                "❌ Автоплатеж отключен\n\n"
                "Все попытки автоматического продления исчерпаны\n"
                f"📅 Подписка истекает через {days_remaining} дней\n\n"
                "🎯 Продлите подписку вручную, чтобы не потерять доступ"
            )
        
        await notification_service.send_notification(
            user_id=autopay.user_id,
            message=message
        )
    
    def _get_error_reason_text(self, error_type: str) -> str:
        """Получение текста причины ошибки"""
        
        reasons = {
            'insufficient_funds': 'Недостаточно средств на карте',
            'card_issue': 'Проблема с картой',
            'technical_error': 'Технический сбой',
            'unknown_error': 'Неизвестная ошибка'
        }
        
        return reasons.get(error_type, 'Ошибка платежа')
    
    async def _handle_max_attempts_reached(self, autopay: AutoPayment):
        """Обработка когда все попытки исчерпаны"""
        
        logger.error(f"❌ Все попытки автоплатежа {autopay.id} исчерпаны")
        
        # Отправляем финальное уведомление
        await notification_service.send_notification(
            user_id=autopay.user_id,
            message=(
                "❌ Автоплатеж отключен\n\n"
                "Не удалось автоматически продлить подписку после нескольких попыток.\n"
                "Продлите подписку вручную в разделе 'Подписка'"
            )
        ) 