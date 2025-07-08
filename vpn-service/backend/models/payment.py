from sqlalchemy import Column, Integer, String, DateTime, Numeric, ForeignKey, Text, Enum, JSON, Float
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