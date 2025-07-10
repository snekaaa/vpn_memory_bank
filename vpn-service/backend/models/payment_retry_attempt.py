from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Boolean, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from config.database import Base
import enum

class RetryResult(str, enum.Enum):
    """Результаты попыток"""
    SUCCESS = "success"
    FAILED = "failed"
    PENDING = "pending"

class PaymentRetryAttempt(Base):
    """Модель попытки повторного платежа"""
    __tablename__ = "payment_retry_attempts"
    
    id = Column(Integer, primary_key=True, index=True)
    auto_payment_id = Column(Integer, ForeignKey("auto_payments.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Информация о попытке
    attempt_number = Column(Integer, nullable=False)
    error_type = Column(String(50), nullable=False)  # 'insufficient_funds', 'technical_error', 'card_issue'
    error_message = Column(Text, nullable=True)  # Полный текст ошибки от Robokassa
    robokassa_response = Column(Text, nullable=True)  # Raw ответ API для дебага
    
    # Временные метки попытки
    scheduled_at = Column(DateTime(timezone=True), nullable=False, index=True)
    attempted_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Результат и планирование
    result = Column(Enum(RetryResult), nullable=True)  # 'success', 'failed', 'pending'
    next_attempt_at = Column(DateTime(timezone=True), nullable=True)
    
    # Уведомления
    user_notified = Column(Boolean, default=False)
    notification_sent_at = Column(DateTime(timezone=True), nullable=True)
    
    # Временная метка создания
    created_at = Column(DateTime(timezone=True), default=func.now())
    
    # Связи
    # auto_payment = relationship("AutoPayment", back_populates="retry_attempts")
    
    def __repr__(self):
        return f"<PaymentRetryAttempt(id={self.id}, auto_payment_id={self.auto_payment_id}, attempt={self.attempt_number}, result={self.result})>"
    
    @property
    def is_successful(self) -> bool:
        """Проверка успешности попытки"""
        return self.result == RetryResult.SUCCESS
    
    @property
    def is_failed(self) -> bool:
        """Проверка неудачной попытки"""
        return self.result == RetryResult.FAILED
    
    @property
    def should_notify_user(self) -> bool:
        """Определение необходимости уведомления пользователя"""
        # Уведомляем после 2-й неудачной попытки
        return self.attempt_number >= 2 and self.is_failed and not self.user_notified 