"""
Trial Automation Service - автоматическое создание триальных счетов

Реализует Registration-Triggered Immediate Trial approach:
- Автоматическое создание платежа за 0₽ при регистрации пользователя
- Предотвращение дублирования триальных периодов
- Настраиваемая длительность триального периода
- Интеграция с PaymentManagementService
- Audit logging всех автоматических операций
"""

import structlog
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from models.user import User
from models.payment import Payment, PaymentMethod, PaymentStatus
from services.payment_management_service import PaymentManagementService

logger = structlog.get_logger("trial_automation")

@dataclass
class TrialConfig:
    """Конфигурация триального периода"""
    trial_days: int = 3
    trial_amount: float = 0.0
    trial_description: str = "Триальный период - {days} дней"
    enabled: bool = True
    max_trials_per_user: int = 1
    admin_user: str = "trial_automation"

class TrialAutomationService:
    """
    Сервис автоматизации триальных аккаунтов
    
    Автоматически создает триальные платежи при регистрации новых пользователей
    с полным контролем дублирования и audit logging.
    """
    
    def __init__(self, payment_service: PaymentManagementService, config: TrialConfig):
        self.payment_service = payment_service
        self.config = config
        self.logger = logger
    
    async def create_trial_for_new_user(
        self,
        user: User,
        db_session: AsyncSession
    ) -> Optional[Payment]:
        """
        Основной entry point для создания триального платежа новому пользователю
        
        Args:
            user: Пользователь для создания триала
            db_session: Database session
            
        Returns:
            Созданный триальный платеж или None если создание не требуется
            
        Raises:
            Exception: При ошибках создания триала
        """
        try:
            # Проверяем, включена ли автоматизация
            if not self.config.enabled:
                self.logger.debug(
                    "Trial automation disabled",
                    user_id=user.id
                )
                return None
            
            # Проверяем eligibility пользователя для триала
            if not await self._is_eligible_for_trial(user, db_session):
                self.logger.info(
                    "User not eligible for trial",
                    user_id=user.id,
                    telegram_id=user.telegram_id
                )
                return None
            
            # Создаем и активируем триальный платеж
            trial_payment = await self._create_and_activate_trial(user, db_session)
            
            return trial_payment
            
        except Exception as e:
            self.logger.error(
                "Failed to create trial for new user",
                user_id=user.id,
                telegram_id=user.telegram_id,
                error=str(e),
                exc_info=True
            )
            raise
    
    async def _is_eligible_for_trial(self, user: User, db_session: AsyncSession) -> bool:
        """
        Проверка права пользователя на триальный период
        
        Критерии eligibility:
        1. У пользователя нет существующих платежей
        2. Не превышен лимит триалов на пользователя
        3. Аккаунт создан недавно (базовая проверка)
        
        Args:
            user: Пользователь для проверки
            db_session: Database session
            
        Returns:
            True если пользователь имеет право на триал
        """
        try:
            # Проверяем существующие платежи пользователя
            existing_payments_count = await db_session.scalar(
                select(func.count(Payment.id)).where(Payment.user_id == user.id)
            )
            
            if existing_payments_count > 0:
                self.logger.debug(
                    "User already has payments, not eligible for trial",
                    user_id=user.id,
                    existing_payments=existing_payments_count
                )
                return False
            
            # Проверяем количество триальных попыток
            trial_payments_count = await db_session.scalar(
                select(func.count(Payment.id))
                .where(Payment.user_id == user.id)
                .where(Payment.amount == 0.0)
                .where(Payment.payment_method.in_([
                    PaymentMethod.manual_trial,
                    PaymentMethod.auto_trial
                ]))
            )
            
            if trial_payments_count >= self.config.max_trials_per_user:
                self.logger.debug(
                    "User exceeded max trials limit",
                    user_id=user.id,
                    trial_payments_count=trial_payments_count,
                    max_allowed=self.config.max_trials_per_user
                )
                return False
            
            # Дополнительная проверка на валидность аккаунта
            if not self._is_valid_user_account(user):
                self.logger.debug(
                    "User account not valid for trial",
                    user_id=user.id,
                    telegram_id=user.telegram_id
                )
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(
                "Error checking trial eligibility",
                user_id=user.id,
                error=str(e),
                exc_info=True
            )
            return False
    
    def _is_valid_user_account(self, user: User) -> bool:
        """
        Проверка валидности аккаунта пользователя
        
        Базовые проверки для предотвращения spam/bot аккаунтов:
        - Наличие telegram_id
        - Активный статус
        - Не заблокирован
        
        Args:
            user: Пользователь для проверки
            
        Returns:
            True если аккаунт валидный
        """
        # Базовые проверки
        if not user.telegram_id:
            return False
        
        if not user.is_active or user.is_blocked:
            return False
        
        # Можно добавить дополнительные проверки:
        # - Возраст аккаунта
        # - Наличие username/first_name
        # - Проверка на подозрительные паттерны
        
        return True
    
    async def _create_and_activate_trial(
        self,
        user: User,
        db_session: AsyncSession
    ) -> Payment:
        """
        Создание и немедленная активация триального платежа
        
        Args:
            user: Пользователь для создания триала
            db_session: Database session
            
        Returns:
            Созданный и активированный триальный платеж
            
        Raises:
            Exception: При ошибках создания или активации
        """
        try:
            # Создаем триальный платеж
            trial_payment = await self.payment_service.create_manual_payment(
                user_id=user.id,
                amount=self.config.trial_amount,
                description=self.config.trial_description.format(days=self.config.trial_days),
                payment_method=PaymentMethod.auto_trial,
                admin_user=self.config.admin_user
            )
            
            # Немедленно активируем триальный платеж
            activated_payment = await self.payment_service.update_payment_status(
                payment_id=trial_payment.id,
                new_status=PaymentStatus.SUCCEEDED,
                admin_user=self.config.admin_user,
                reason="Auto-activation of trial payment"
            )
            
            self.logger.info(
                "Trial payment created and activated",
                user_id=user.id,
                telegram_id=user.telegram_id,
                payment_id=trial_payment.id,
                trial_days=self.config.trial_days,
                amount=self.config.trial_amount
            )
            
            return activated_payment
            
        except Exception as e:
            self.logger.error(
                "Failed to create and activate trial payment",
                user_id=user.id,
                telegram_id=user.telegram_id,
                error=str(e),
                exc_info=True
            )
            raise
    
    async def get_trial_statistics(self, db_session: AsyncSession) -> Dict[str, Any]:
        """
        Получение статистики по автоматическим триалам
        
        Args:
            db_session: Database session
            
        Returns:
            Словарь со статистикой триалов
        """
        try:
            # Общее количество автоматических триалов
            total_auto_trials = await db_session.scalar(
                select(func.count(Payment.id))
                .where(Payment.payment_method == PaymentMethod.auto_trial)
            )
            
            # Количество успешных триалов
            successful_trials = await db_session.scalar(
                select(func.count(Payment.id))
                .where(Payment.payment_method == PaymentMethod.auto_trial)
                .where(Payment.status == PaymentStatus.SUCCEEDED)
            )
            
            # Триалы за последние 24 часа
            recent_trials = await db_session.scalar(
                select(func.count(Payment.id))
                .where(Payment.payment_method == PaymentMethod.auto_trial)
                .where(Payment.created_at >= datetime.now(timezone.utc) - timezone.utc.localize(datetime.now()).utctimetuple()
                )
            )
            
            statistics = {
                "total_auto_trials": total_auto_trials or 0,
                "successful_trials": successful_trials or 0,
                "recent_trials_24h": recent_trials or 0,
                "success_rate": (successful_trials / total_auto_trials * 100) if total_auto_trials > 0 else 0,
                "config": {
                    "trial_days": self.config.trial_days,
                    "trial_amount": self.config.trial_amount,
                    "enabled": self.config.enabled,
                    "max_trials_per_user": self.config.max_trials_per_user
                }
            }
            
            self.logger.info(
                "Trial statistics retrieved",
                **statistics
            )
            
            return statistics
            
        except Exception as e:
            self.logger.error(
                "Failed to get trial statistics",
                error=str(e),
                exc_info=True
            )
            return {}


def get_default_trial_config() -> TrialConfig:
    """
    Получение конфигурации триального периода по умолчанию
    
    Returns:
        Конфигурация с настройками по умолчанию
    """
    return TrialConfig(
        trial_days=3,
        trial_amount=0.0,
        trial_description="Автоматический триальный период - {days} дней",
        enabled=True,
        max_trials_per_user=1,
        admin_user="auto_trial_system"
    )


async def get_trial_config_from_db(db_session: AsyncSession) -> TrialConfig:
    """
    Получение конфигурации триального периода из базы данных
    
    Args:
        db_session: Database session
        
    Returns:
        Конфигурация с настройками из базы данных
    """
    try:
        from services.app_settings_service import AppSettingsService
        
        settings = await AppSettingsService.get_settings(db_session)
        
        return TrialConfig(
            trial_days=settings.trial_days,
            trial_amount=0.0,
            trial_description="Автоматический триальный период - {days} дней",
            enabled=settings.trial_enabled,
            max_trials_per_user=settings.trial_max_per_user,
            admin_user="auto_trial_system"
        )
    except Exception as e:
        logger.error("Failed to get trial config from DB, using default", error=str(e))
        return get_default_trial_config()


async def get_trial_automation_service(
    payment_service: PaymentManagementService,
    config: Optional[TrialConfig] = None,
    db_session: Optional[AsyncSession] = None
) -> TrialAutomationService:
    """
    Factory function для получения TrialAutomationService
    
    Args:
        payment_service: Сервис управления платежами
        config: Конфигурация триала (если не указана, берется из БД или по умолчанию)
        db_session: Database session для получения настроек из БД
        
    Returns:
        Экземпляр TrialAutomationService
    """
    if config is None:
        if db_session is not None:
            config = await get_trial_config_from_db(db_session)
        else:
            config = get_default_trial_config()
    
    return TrialAutomationService(payment_service, config) 