from sqlalchemy import Column, Integer, String, DateTime, Boolean, Numeric, ForeignKey, Text, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from config.database import Base
import enum

class SubscriptionStatus(str, enum.Enum):
    """Статусы подписки"""
    ACTIVE = "active"
    EXPIRED = "expired"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"

class SubscriptionType(str, enum.Enum):
    """Типы подписок"""
    TRIAL = "trial"        # Пробная
    MONTHLY = "monthly"    # Месячная
    QUARTERLY = "quarterly"  # Квартальная
    SEMI_ANNUAL = "semi_annual"  # Полугодовая
    YEARLY = "yearly"      # Годовая

class Subscription(Base):
    """Модель подписки VPN"""
    __tablename__ = "subscriptions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Тип и статус подписки
    subscription_type = Column(Enum(SubscriptionType), nullable=False)
    status = Column(Enum(SubscriptionStatus), default=SubscriptionStatus.ACTIVE)
    
    # Финансовые данные
    price = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), default="RUB")
    
    # Временные рамки
    start_date = Column(DateTime(timezone=True), server_default=func.now())
    end_date = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Дополнительные параметры
    auto_renewal = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)
    
    # Связи (упрощенная архитектура - убрана back_populates с subscriptions)
    # user = relationship("User")  # Закомментировано для избежания circular imports
    # payments = relationship("Payment", back_populates="subscription")  # Закомментировано
    
    def __repr__(self):
        return f"<Subscription(id={self.id}, user_id={self.user_id}, type={self.subscription_type}, status={self.status})>"
    
    @property
    def is_active(self) -> bool:
        """Проверка активности подписки"""
        from datetime import datetime, timezone
        return (
            self.status == SubscriptionStatus.ACTIVE and
            self.end_date > datetime.now(timezone.utc)
        )
    
    @property
    def days_remaining(self) -> int:
        """Количество дней до окончания подписки"""
        from datetime import datetime, timezone
        if self.end_date:
            delta = self.end_date - datetime.now(timezone.utc)
            return max(0, delta.days)
        return 0
    
    @property
    def plan_name(self) -> str:
        """Название плана подписки"""
        plan_names = {
            SubscriptionType.TRIAL: "Пробная подписка (7 дней)",
            SubscriptionType.MONTHLY: "Месячная подписка",
            SubscriptionType.QUARTERLY: "Квартальная подписка (3 месяца)",
            SubscriptionType.SEMI_ANNUAL: "Полугодовая подписка",
            SubscriptionType.YEARLY: "Годовая подписка"
        }
        return plan_names.get(self.subscription_type, "Подписка") 