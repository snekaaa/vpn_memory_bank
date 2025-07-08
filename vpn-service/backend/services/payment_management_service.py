"""
Payment Management Service - ручное управление платежами в админ панели

Реализует Service Layer Pattern для безопасного управления платежами:
- Создание платежей вручную (включая триальные за 0₽)
- Изменение статуса платежей с автоматическим продлением подписки
- Audit logging всех операций
- Транзакционная безопасность для financial operations
"""

import structlog
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from sqlalchemy.orm import selectinload

from models.payment import Payment, PaymentStatus, PaymentMethod
from models.user import User, UserSubscriptionStatus
from config.database import get_db_session

logger = structlog.get_logger("payment_management")

class PaymentManagementService:
    """
    Сервис ручного управления платежами
    
    Предоставляет безопасные методы для создания и управления платежами
    с полным audit logging и транзакционной безопасностью.
    """
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self.logger = logger
    
    async def create_manual_payment(
        self,
        user_id: int,
        amount: float,
        description: str,
        payment_method: PaymentMethod,
        admin_user: str,
        subscription_days: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Payment:
        """
        Создание ручного платежа администратором
        
        Этот метод позволяет админу создавать платеж для пользователя без внешних платежных систем.
        Платеж создается в статусе PENDING и требует дальнейшего подтверждения через
        update_payment_status() для активации подписки.
        
        Args:
            user_id: ID пользователя в Telegram
            amount: Сумма платежа
            description: Описание платежа
            payment_method: Метод платежа (manual_admin, manual_trial, etc.)
            admin_user: Пользователь, создающий платеж (для audit)
            subscription_days: Количество дней подписки (если не указано, расчитывается автоматически)
            metadata: Дополнительные метаданные
            
        Returns:
            Созданный платеж
            
        Raises:
            ValueError: При некорректных входных данных
            Exception: При ошибках создания
        """
        try:
            # Валидация входных данных
            await self._validate_payment_creation_data(user_id, amount, payment_method)
            
            # Проверяем существование пользователя
            user = await self._get_user_or_raise(user_id)
            
            # Подготавливаем метаданные с количеством дней
            payment_metadata = metadata or {}
            if subscription_days:
                payment_metadata["subscription_days"] = subscription_days
            
            # Создаем платеж
            payment = Payment(
                user_id=user_id,
                amount=amount,
                currency="RUB",
                status=PaymentStatus.PENDING,  # Создаем в статусе PENDING
                payment_method=payment_method,
                description=description,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                payment_metadata=payment_metadata
            )
            
            self.db.add(payment)
            await self.db.flush()  # Получаем ID платежа
            
            # Audit logging
            await self._log_payment_operation(
                operation="CREATE_MANUAL_PAYMENT",
                payment_id=payment.id,
                admin_user=admin_user,
                details={
                    "user_id": user_id,
                    "amount": amount,
                    "payment_method": payment_method.value,
                    "description": description,
                    "subscription_days": subscription_days,
                    "metadata": metadata
                }
            )
            
            self.logger.info(
                "Manual payment created",
                payment_id=payment.id,
                user_id=user_id,
                amount=amount,
                payment_method=payment_method.value,
                admin_user=admin_user
            )
            
            return payment
            
        except Exception as e:
            self.logger.error(
                "Failed to create manual payment",
                user_id=user_id,
                amount=amount,
                admin_user=admin_user,
                error=str(e),
                exc_info=True
            )
            raise
    
    async def update_payment_status(
        self,
        payment_id: int,
        new_status: PaymentStatus,
        admin_user: str,
        reason: Optional[str] = None
    ) -> Payment:
        """
        Обновление статуса платежа с бизнес-логикой
        
        При изменении статуса на SUCCEEDED автоматически продлевает подписку пользователя.
        
        Args:
            payment_id: ID платежа
            new_status: Новый статус платежа
            admin_user: Пользователь, изменяющий статус
            reason: Причина изменения статуса
            
        Returns:
            Обновленный платеж
            
        Raises:
            ValueError: При некорректных данных
            Exception: При ошибках обновления
        """
        try:
            # Получаем платеж
            payment = await self._get_payment_or_raise(payment_id)
            old_status = payment.status
            
            # Валидация изменения статуса
            await self._validate_payment_status_change(payment, new_status)
            
            # Обновляем статус
            payment.status = new_status
            payment.updated_at = datetime.now(timezone.utc)
            
            # Если статус изменился на SUCCEEDED, продлеваем подписку
            extended_user = None
            if (new_status == PaymentStatus.SUCCEEDED and 
                old_status != PaymentStatus.SUCCEEDED):
                
                extended_user = await self._extend_user_subscription(payment)
                
                # Устанавливаем дату оплаты
                payment.paid_at = datetime.now(timezone.utc)
                payment.processed_at = datetime.now(timezone.utc)
            
            # Audit logging
            await self._log_payment_operation(
                operation="UPDATE_PAYMENT_STATUS",
                payment_id=payment_id,
                admin_user=admin_user,
                details={
                    "old_status": old_status.value,
                    "new_status": new_status.value,
                    "reason": reason,
                    "subscription_extended": extended_user is not None,
                    "user_id": payment.user_id
                }
            )
            
            self.logger.info(
                "Payment status updated",
                payment_id=payment_id,
                user_id=payment.user_id,
                old_status=old_status.value,
                new_status=new_status.value,
                admin_user=admin_user,
                subscription_extended=extended_user is not None
            )
            
            return payment
            
        except Exception as e:
            self.logger.error(
                "Failed to update payment status",
                payment_id=payment_id,
                new_status=new_status.value,
                admin_user=admin_user,
                error=str(e),
                exc_info=True
            )
            raise
    
    async def get_user_payments_history(
        self,
        user_id: int,
        limit: int = 50,
        offset: int = 0
    ) -> List[Payment]:
        """
        Получение истории платежей пользователя
        
        Args:
            user_id: ID пользователя
            limit: Количество записей
            offset: Смещение для пагинации
            
        Returns:
            Список платежей пользователя
        """
        try:
            result = await self.db.execute(
                select(Payment)
                .where(Payment.user_id == user_id)
                .order_by(Payment.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            
            payments = result.scalars().all()
            
            self.logger.debug(
                "Retrieved user payments history",
                user_id=user_id,
                payments_count=len(payments),
                limit=limit,
                offset=offset
            )
            
            return list(payments)
            
        except Exception as e:
            self.logger.error(
                "Failed to get user payments history",
                user_id=user_id,
                error=str(e),
                exc_info=True
            )
            raise
    
    async def _extend_user_subscription(self, payment: Payment) -> Optional[User]:
        """
        Продление подписки пользователя на основе платежа
        
        Args:
            payment: Платеж для обработки
            
        Returns:
            Обновленный пользователь или None если продление не требуется
        """
        try:
            # Получаем пользователя
            user = await self._get_user_or_raise(payment.user_id)
            
            # Рассчитываем количество дней для продления
            days_to_extend = self._calculate_subscription_days(payment)
            
            if days_to_extend <= 0:
                return None
            
            # Продлеваем подписку
            user.extend_subscription(days_to_extend)
            
            self.logger.info(
                "User subscription extended",
                user_id=payment.user_id,
                payment_id=payment.id,
                days_extended=days_to_extend,
                new_valid_until=user.valid_until
            )
            
            return user
            
        except Exception as e:
            self.logger.error(
                "Failed to extend user subscription",
                payment_id=payment.id,
                user_id=payment.user_id,
                error=str(e),
                exc_info=True
            )
            raise
    
    def _calculate_subscription_days(self, payment: Payment) -> int:
        """
        Расчет количества дней для продления подписки
        
        Приоритет расчета:
        1. Если в metadata указано subscription_days - используем его
        2. Иначе используем логику по сумме платежа
        
        Логика расчета по сумме:
        - Триальные платежи (0₽): 3 дня
        - Месячные платежи (100₽): 30 дней
        - Квартальные платежи (300₽): 90 дней
        - Другие суммы: пропорционально (100₽ = 30 дней)
        
        Args:
            payment: Платеж для анализа
            
        Returns:
            Количество дней для продления
        """
        # Проверяем metadata на наличие subscription_days
        if payment.payment_metadata and 'subscription_days' in payment.payment_metadata:
            subscription_days = payment.payment_metadata['subscription_days']
            if isinstance(subscription_days, int) and subscription_days > 0:
                return subscription_days
        
        # Расчет по сумме платежа
        amount = payment.amount
        
        # Триальные платежи
        if amount == 0.0:
            return 3
        
        # Стандартные планы
        if amount == 100.0:
            return 30  # Месячный
        elif amount == 300.0:
            return 90  # Квартальный
        elif amount == 1000.0:
            return 365  # Годовой
        
        # Пропорциональный расчет для нестандартных сумм
        # Базовая ставка: 100₽ = 30 дней
        days_per_100_rub = 30
        calculated_days = int((amount / 100.0) * days_per_100_rub)
        
        return max(calculated_days, 1)  # Минимум 1 день
    
    async def _validate_payment_creation_data(
        self,
        user_id: int,
        amount: float,
        payment_method: PaymentMethod
    ) -> None:
        """Валидация данных для создания платежа"""
        
        if user_id <= 0:
            raise ValueError("Invalid user_id")
        
        if amount < 0:
            raise ValueError("Amount cannot be negative")
        
        if not isinstance(payment_method, PaymentMethod):
            raise ValueError("Invalid payment_method")
        
        # Дополнительные валидации для ручных методов
        manual_methods = {
            PaymentMethod.manual_admin,
            PaymentMethod.manual_trial,
            PaymentMethod.auto_trial,
            PaymentMethod.manual_correction
        }
        
        if payment_method not in manual_methods:
            raise ValueError(f"Payment method {payment_method} is not supported for manual creation")
    
    async def _validate_payment_status_change(
        self,
        payment: Payment,
        new_status: PaymentStatus
    ) -> None:
        """Валидация изменения статуса платежа"""
        
        # Проверяем, что новый статус отличается от текущего
        if payment.status == new_status:
            raise ValueError(f"Payment already has status {new_status}")
        
        # Проверяем допустимые переходы статусов
        allowed_transitions = {
            PaymentStatus.PENDING: {PaymentStatus.SUCCEEDED, PaymentStatus.FAILED, PaymentStatus.CANCELLED},
            PaymentStatus.PROCESSING: {PaymentStatus.SUCCEEDED, PaymentStatus.FAILED, PaymentStatus.CANCELLED},
            PaymentStatus.FAILED: {PaymentStatus.SUCCEEDED, PaymentStatus.CANCELLED},
            PaymentStatus.CANCELLED: {PaymentStatus.SUCCEEDED},
            PaymentStatus.SUCCEEDED: {PaymentStatus.REFUNDED, PaymentStatus.CANCELLED},
            PaymentStatus.REFUNDED: set()  # Из REFUNDED никуда нельзя
        }
        
        current_status = payment.status
        if new_status not in allowed_transitions.get(current_status, set()):
            raise ValueError(
                f"Invalid status transition from {current_status} to {new_status}"
            )
    
    async def _get_user_or_raise(self, user_id: int) -> User:
        """Получение пользователя или вызов исключения"""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise ValueError(f"User with id {user_id} not found")
        
        return user
    
    async def _get_payment_or_raise(self, payment_id: int) -> Payment:
        """Получение платежа или вызов исключения"""
        result = await self.db.execute(
            select(Payment).where(Payment.id == payment_id)
        )
        payment = result.scalar_one_or_none()
        
        if not payment:
            raise ValueError(f"Payment with id {payment_id} not found")
        
        return payment
    
    async def _log_payment_operation(
        self,
        operation: str,
        payment_id: int,
        admin_user: str,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Комплексный audit logging операций с платежами
        
        Args:
            operation: Тип операции (CREATE_MANUAL_PAYMENT, UPDATE_PAYMENT_STATUS, etc.)
            payment_id: ID платежа
            admin_user: Пользователь, выполняющий операцию
            details: Дополнительные детали операции
        """
        try:
            log_entry = {
                "operation": operation,
                "payment_id": payment_id,
                "admin_user": admin_user,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "details": details or {}
            }
            
            # Логируем в structured log
            self.logger.info(
                f"Payment operation: {operation}",
                **log_entry
            )
            
            # Можно добавить сохранение в отдельную audit таблицу
            # await self._save_audit_log(log_entry)
            
        except Exception as e:
            # Ошибки логирования не должны прерывать основной процесс
            self.logger.error(
                "Failed to log payment operation",
                operation=operation,
                payment_id=payment_id,
                admin_user=admin_user,
                error=str(e)
            )


def get_payment_management_service(db_session: AsyncSession) -> PaymentManagementService:
    """
    Factory function для получения PaymentManagementService
    
    Args:
        db_session: Database session
        
    Returns:
        Экземпляр PaymentManagementService
    """
    return PaymentManagementService(db_session) 