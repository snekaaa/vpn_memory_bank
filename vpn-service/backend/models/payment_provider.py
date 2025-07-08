"""
Модель платежного провайдера для системы управления платежными системами
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, JSON, Text, Float, Enum, Numeric
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from config.database import Base
import enum
from datetime import datetime
from typing import Dict, Any, Optional

class PaymentProviderType(str, enum.Enum):
    """Типы платежных провайдеров"""
    robokassa = "robokassa"
    freekassa = "freekassa"
    yookassa = "yookassa"
    coingate = "coingate"
    paypal = "paypal"
    stripe = "stripe"
    sberbank = "sberbank"
    tinkoff = "tinkoff"

class PaymentProviderStatus(str, enum.Enum):
    """Статусы платежных провайдеров"""
    active = "active"
    inactive = "inactive"
    testing = "testing"
    error = "error"
    maintenance = "maintenance"

class PaymentProvider(Base):
    """
    Модель платежного провайдера
    
    Хранит конфигурацию и настройки для различных платежных систем
    """
    __tablename__ = "payment_providers"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)  # Название провайдера (например, "Основная Робокасса")
    provider_type = Column(Enum(PaymentProviderType, name="payment_provider_type"), nullable=False)  # Тип провайдера
    
    # Статус и режим работы
    status = Column(Enum(PaymentProviderStatus, name="payment_provider_status"), default=PaymentProviderStatus.inactive)
    is_active = Column(Boolean, default=False)  # Активен ли провайдер
    is_test_mode = Column(Boolean, default=True)  # Тестовый режим
    is_default = Column(Boolean, default=False)  # Провайдер по умолчанию
    
    # Конфигурация (JSON с настройками для каждого типа провайдера)
    config = Column(JSON, nullable=False, default=dict)
    
    # Описание и метаданные
    description = Column(Text, nullable=True)
    webhook_url = Column(String(500), nullable=True)  # URL для webhook'ов
    
    # Приоритет (для сортировки)
    priority = Column(Integer, default=100)
    
    # Payment limits and commission
    min_amount = Column(Numeric(10, 2), default=1.00)
    max_amount = Column(Numeric(10, 2), default=100000.00)
    commission_percent = Column(Numeric(5, 2), default=0.00)
    commission_fixed = Column(Numeric(10, 2), default=0.00)
    
    # URL configuration for redirects and notifications
    success_url = Column(String(500), nullable=True)
    failure_url = Column(String(500), nullable=True) 
    notification_url = Column(String(500), nullable=True)
    notification_method = Column(String(10), default='POST')
    
    # Статистика
    total_payments = Column(Integer, default=0)
    successful_payments = Column(Integer, default=0)
    failed_payments = Column(Integer, default=0)
    total_amount = Column(Float, default=0.0)
    
    # Временные метки
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Связи - закомментированы для избежания circular imports
    # payments = relationship("Payment", back_populates="provider")
    
    def __repr__(self):
        return f"<PaymentProvider(id={self.id}, name='{self.name}', type={self.provider_type}, status={self.status})>"
    
    @property
    def success_rate(self) -> float:
        """Процент успешных платежей"""
        if self.total_payments == 0:
            return 0.0
        return (self.successful_payments / self.total_payments) * 100
    
    @property
    def is_healthy(self) -> bool:
        """Проверка состояния провайдера"""
        if not self.is_active:
            return False
        if self.status == PaymentProviderStatus.error:
            return False
        return True
    
    @property
    def display_name(self) -> str:
        """Отображаемое имя провайдера"""
        suffix = ""
        if self.is_test_mode:
            suffix = " (Тест)"
        if not self.is_active:
            suffix += " (Отключен)"
        return f"{self.name}{suffix}"
    
    def get_config_value(self, key: str, default: Any = None) -> Any:
        """Получение значения из конфигурации"""
        return self.config.get(key, default)
    
    def set_config_value(self, key: str, value: Any) -> None:
        """Установка значения в конфигурацию"""
        if self.config is None:
            self.config = {}
        self.config[key] = value
    
    def update_payment_stats(self, amount: float, success: bool) -> None:
        """Обновление статистики платежей"""
        self.total_payments += 1
        self.total_amount += amount
        
        if success:
            self.successful_payments += 1
        else:
            self.failed_payments += 1
    
    def get_robokassa_config(self) -> Dict[str, Any]:
        """Получение конфигурации для Робокассы"""
        if self.provider_type != PaymentProviderType.robokassa:
            return {}
        
        return {
            "shop_id": self.get_config_value("shop_id"),
            "password1": self.get_config_value("password1"),
            "password2": self.get_config_value("password2"),
            "base_url": self.get_config_value("base_url", "https://auth.robokassa.ru/Merchant/Index.aspx"),
            "test_mode": self.is_test_mode
        }
    
    def get_freekassa_config(self) -> Dict[str, Any]:
        """Получение конфигурации для FreeKassa"""
        if self.provider_type != PaymentProviderType.freekassa:
            return {}
        
        return {
            "merchant_id": self.get_config_value("merchant_id"),  # Добавляем merchant_id
            "api_key": self.get_config_value("api_key"),
            "secret1": self.get_config_value("secret1"),
            "secret2": self.get_config_value("secret2"),
            "test_mode": self.is_test_mode,
            "confirmation_mode": self.get_config_value("confirmation_mode", True),
            "success_url": self.success_url,
            "failure_url": self.failure_url,
            "notification_url": self.notification_url,
            "notification_method": self.notification_method
        }
    
    def get_yookassa_config(self) -> Dict[str, Any]:
        """Получение конфигурации для ЮKassa"""
        if self.provider_type != PaymentProviderType.yookassa:
            return {}
        
        return {
            "shop_id": self.get_config_value("shop_id"),
            "api_key": self.get_config_value("api_key"),
            "test_mode": self.is_test_mode
        }
    
    def validate_config(self) -> tuple[bool, str]:
        """Валидация конфигурации провайдера"""
        if not self.config:
            return False, "Конфигурация не задана"
        
        if self.provider_type == PaymentProviderType.robokassa:
            required_fields = ["shop_id", "password1", "password2"]
            for field in required_fields:
                if not self.get_config_value(field):
                    return False, f"Поле {field} обязательно для Робокассы"
        
        elif self.provider_type == PaymentProviderType.freekassa:
            required_fields = ["merchant_id", "api_key", "secret1", "secret2"]
            for field in required_fields:
                if not self.get_config_value(field):
                    return False, f"Поле {field} обязательно для FreeKassa"
            
            # Validate notification method
            if self.notification_method not in ['GET', 'POST']:
                return False, "Метод уведомления должен быть GET или POST"
        
        elif self.provider_type == PaymentProviderType.yookassa:
            required_fields = ["shop_id", "api_key"]
            for field in required_fields:
                if not self.get_config_value(field):
                    return False, f"Поле {field} обязательно для ЮKassa"
        
        return True, "Конфигурация корректна"
    
    def mask_sensitive_config(self) -> Dict[str, Any]:
        """Получение конфигурации с замаскированными чувствительными данными"""
        if not self.config:
            return {}
        
        masked_config = self.config.copy()
        sensitive_fields = ["password1", "password2", "api_key", "secret_key", "secret1", "secret2"]
        
        for field in sensitive_fields:
            if field in masked_config and masked_config[field]:
                value = str(masked_config[field])
                if len(value) > 6:
                    masked_config[field] = "••••••" + value[-4:]
                else:
                    masked_config[field] = "••••••"
        
        return masked_config 