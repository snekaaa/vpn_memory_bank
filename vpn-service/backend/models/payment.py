from sqlalchemy import Column, Integer, String, DateTime, Numeric, ForeignKey, Text, Enum, JSON, Float, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from config.database import Base
import enum
from datetime import datetime

class PaymentStatus(str, enum.Enum):
    """Статусы платежа"""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"

class PaymentMethod(str, enum.Enum):
    """Методы платежа"""
    YOOKASSA_CARD = "YOOKASSA_CARD"        # Банковская карта через ЮKassa
    YOOKASSA_SBP = "YOOKASSA_SBP"          # СБП через ЮKassa
    YOOKASSA_WALLET = "YOOKASSA_WALLET"    # Электронные кошельки
    COINGATE_CRYPTO = "COINGATE_CRYPTO"    # Криптовалюта через CoinGate
    robokassa = "robokassa"                # Робокасса (все методы)
    freekassa = "freekassa"                # FreeKassa (все методы)
    # Manual payment methods
    manual_admin = "manual_admin"          # Ручное создание администратором
    manual_trial = "manual_trial"          # Ручной триальный платеж
    auto_trial = "auto_trial"              # Автоматический триальный платеж
    manual_correction = "manual_correction" # Ручная корректировка платежа

class RecurringStatus(str, enum.Enum):
    """Статусы рекуррентных платежей"""
    INACTIVE = "inactive"
    ACTIVE = "active"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    FAILED = "failed"

class Payment(Base):
    """Модель платежа"""
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=True)
    provider_id = Column(Integer, ForeignKey("payment_providers.id"), nullable=True)
    
    # Основные данные платежа
    external_id = Column(String(255), unique=True, index=True)  # ID в платежной системе
    amount = Column(Float, nullable=False)
    currency = Column(String(3), default="RUB")
    
    # Статус и метод
    status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING)
    payment_method = Column(Enum(PaymentMethod), nullable=False)
    
    # Дополнительные поля
    payment_system_data = Column(String, nullable=True)
    confirmation_url = Column(String, nullable=True)
    external_payment_id = Column(String, nullable=True)
    external_data = Column(JSON, nullable=True)
    
    # Робокасса специфичные поля
    robokassa_invoice_id = Column(String, nullable=True)
    robokassa_signature = Column(String, nullable=True)
    robokassa_payment_method = Column(String, nullable=True)
    
    # Поля для рекуррентных платежей
    robokassa_recurring_id = Column(String, nullable=True)  # ID рекуррентного платежа в Robokassa
    is_recurring_enabled = Column(Boolean, default=False)
    recurring_period_days = Column(Integer, nullable=True)
    next_payment_date = Column(DateTime(timezone=True), nullable=True)
    recurring_status = Column(Enum(RecurringStatus), default=RecurringStatus.INACTIVE)
    is_recurring_setup = Column(Boolean, default=False)  # Флаг первого платежа для setup
    
    # Поля для автоплатежей
    is_autopay_generated = Column(Boolean, default=False)  # Флаг автоматически созданного платежа
    autopay_attempt_number = Column(Integer, nullable=True)  # Номер попытки автоплатежа
    autopay_parent_payment_id = Column(Integer, ForeignKey('payments.id'), nullable=True)  # Связь с первым платежом
    
    # Временные метки
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    paid_at = Column(DateTime(timezone=True), nullable=True)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Дополнительная информация
    description = Column(String, nullable=True)
    failure_reason = Column(String, nullable=True)
    payment_metadata = Column(JSON, nullable=True)
    
    # Связи - закомментированы для избежания circular imports
    # user = relationship("User", back_populates="payments")
    # subscription = relationship("Subscription", back_populates="payments")  
    # provider = relationship("PaymentProvider", back_populates="payments")
    # child_autopayments = relationship("Payment", backref="parent_payment", foreign_keys=[autopay_parent_payment_id])
    
    def __repr__(self):
        return f"<Payment(id={self.id}, user_id={self.user_id}, amount={self.amount}, status={self.status})>"
    
    @property
    def is_successful(self) -> bool:
        """Проверка успешности платежа"""
        return self.status == PaymentStatus.SUCCEEDED
    
    @property
    def is_pending(self) -> bool:
        """Проверка ожидания платежа"""
        return self.status in [PaymentStatus.PENDING, PaymentStatus.PROCESSING]
    
    @property
    def is_robokassa_payment(self) -> bool:
        """Проверка, является ли платеж через Робокассу"""
        return self.payment_method == PaymentMethod.robokassa 