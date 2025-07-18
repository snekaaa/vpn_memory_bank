from sqlalchemy import Column, Integer, String, DateTime, Boolean, BigInteger, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from config.database import Base
import enum

class UserSubscriptionStatus(str, enum.Enum):
    """Статусы подписки пользователя"""
    none = "none"           # Нет подписки
    active = "active"       # Активная подписка
    expired = "expired"     # Подписка истекла
    suspended = "suspended" # Подписка приостановлена

class User(Base):
    """Модель пользователя"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(BigInteger, unique=True, index=True, nullable=False)
    username = Column(String(255), index=True)
    first_name = Column(String(255))
    last_name = Column(String(255))
    language_code = Column(String(10), default="ru")
    
    # Статус пользователя
    is_active = Column(Boolean, default=True)
    is_blocked = Column(Boolean, default=False)
    
    # Подписка пользователя (упрощенная архитектура)
    subscription_status = Column(Enum(UserSubscriptionStatus, name="user_subscription_status"), default=UserSubscriptionStatus.active)
    valid_until = Column(DateTime(timezone=True), nullable=True)
    
    # Настройки автоплатежей
    autopay_enabled = Column(Boolean, default=True)
    
    # Временные метки
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_activity = Column(DateTime(timezone=True), server_default=func.now())
    
    # Реферальная система
    referrer_id = Column(Integer, index=True, nullable=True)
    referral_code = Column(String(20), unique=True, index=True)
    
    # Связи - закомментированы для избежания circular imports
    # payments = relationship("Payment", back_populates="user", lazy="select")
    # subscriptions связь удалена - упрощенная архитектура
    
    def __repr__(self):
        return f"<User(id={self.id}, telegram_id={self.telegram_id}, username={self.username})>"
    
    @property
    def has_active_subscription(self) -> bool:
        """Проверка активной подписки (упрощенная логика)"""
        from datetime import datetime, timezone
        return (
            self.subscription_status == 'active' and
            self.valid_until and
            self.valid_until > datetime.now(timezone.utc)
        )
    
    @property
    def subscription_days_remaining(self) -> int:
        """Количество дней до окончания действия аккаунта"""
        from datetime import datetime, timezone
        if self.valid_until and self.subscription_status == 'active':
            delta = self.valid_until - datetime.now(timezone.utc)
            return max(0, delta.days)
        return 0
    
    def extend_subscription(self, days: int) -> None:
        """Продлить действие аккаунта на указанное количество дней"""
        from datetime import datetime, timezone, timedelta
        if self.valid_until and self.valid_until > datetime.now(timezone.utc):
            # Продлеваем от текущей даты окончания
            self.valid_until += timedelta(days=days)
        else:
            # Начинаем от текущего времени
            self.valid_until = datetime.now(timezone.utc) + timedelta(days=days)
        self.subscription_status = 'active' 