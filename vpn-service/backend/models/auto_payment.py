from sqlalchemy import Column, Integer, String, DateTime, Numeric, ForeignKey, Boolean, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from config.database import Base
import enum

class AutoPaymentStatus(str, enum.Enum):
    """Статусы автоплатежа"""
    INACTIVE = "inactive"
    ACTIVE = "active"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    FAILED = "failed"

class AutoPayment(Base):
    """Модель автоплатежа"""
    __tablename__ = "auto_payments"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id", ondelete="SET NULL"), nullable=True, index=True)
    payment_id = Column(Integer, ForeignKey("payments.id", ondelete="SET NULL"), nullable=True)
    
    # Данные рекуррентного платежа
    robokassa_recurring_id = Column(String(255), unique=True, nullable=True)
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), default="RUB")
    period_days = Column(Integer, nullable=False)
    
    # Планирование
    next_payment_date = Column(DateTime(timezone=True), nullable=False, index=True)
    status = Column(Enum(AutoPaymentStatus), default=AutoPaymentStatus.INACTIVE, index=True)
    
    # Статистика попыток
    attempts_count = Column(Integer, default=0)
    last_attempt_date = Column(DateTime(timezone=True), nullable=True)
    last_error_type = Column(String(50), nullable=True)
    is_recurring_id_valid = Column(Boolean, default=True)
    
    # Временные метки
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    
    # Связи
    # user = relationship("User", back_populates="auto_payments")
    # subscription = relationship("Subscription", back_populates="auto_payment", uselist=False)
    # payment = relationship("Payment")
    # retry_attempts = relationship("PaymentRetryAttempt", back_populates="auto_payment", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<AutoPayment(id={self.id}, user_id={self.user_id}, amount={self.amount}, status={self.status})>"
    
    @property
    def is_active(self) -> bool:
        """Проверка активности автоплатежа"""
        return self.status == AutoPaymentStatus.ACTIVE
    
    @property
    def can_be_charged(self) -> bool:
        """Проверка возможности списания"""
        return self.is_active and self.is_recurring_id_valid 