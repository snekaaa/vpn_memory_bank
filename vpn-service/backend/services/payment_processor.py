"""
Абстрактный базовый класс для платежных процессоров
Реализует Factory pattern для создания процессоров различных платежных систем
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime
import logging

from models.payment_provider import PaymentProvider, PaymentProviderType


@dataclass
class PaymentRequest:
    """Запрос на создание платежа"""
    user_id: int
    amount: float
    currency: str = "RUB"
    description: str = ""
    return_url: str = ""
    webhook_url: str = ""
    metadata: Dict[str, Any] = None


@dataclass
class PaymentResponse:
    """Ответ на запрос создания платежа"""
    success: bool
    payment_id: Optional[str] = None
    confirmation_url: Optional[str] = None
    external_payment_id: Optional[str] = None
    error_message: Optional[str] = None
    provider_data: Dict[str, Any] = None


@dataclass
class WebhookData:
    """Данные webhook уведомления"""
    provider_id: int
    external_payment_id: str
    status: str
    amount: float
    currency: str = "RUB"
    metadata: Dict[str, Any] = None
    raw_data: Dict[str, Any] = None


@dataclass
class PaymentStatus:
    """Статус платежа"""
    external_payment_id: str
    status: str
    amount: float
    currency: str = "RUB"
    paid_at: Optional[datetime] = None
    error_message: Optional[str] = None
    provider_data: Dict[str, Any] = None


class PaymentProcessor(ABC):
    """
    Абстрактный базовый класс для платежных процессоров
    
    Каждый платежный провайдер должен реализовать этот интерфейс
    """
    
    def __init__(self, provider: PaymentProvider):
        self.provider = provider
        self.logger = logging.getLogger(f"{self.__class__.__name__}")
    
    @abstractmethod
    async def create_payment(self, request: PaymentRequest) -> PaymentResponse:
        """
        Создание платежа в платежной системе
        
        Args:
            request: Запрос на создание платежа
            
        Returns:
            PaymentResponse: Ответ с данными созданного платежа
        """
        pass
    
    @abstractmethod
    async def check_payment_status(self, external_payment_id: str) -> PaymentStatus:
        """
        Проверка статуса платежа
        
        Args:
            external_payment_id: ID платежа в платежной системе
            
        Returns:
            PaymentStatus: Статус платежа
        """
        pass
    
    @abstractmethod
    async def process_webhook(self, webhook_data: Dict[str, Any]) -> WebhookData:
        """
        Обработка webhook уведомления
        
        Args:
            webhook_data: Данные webhook от платежной системы
            
        Returns:
            WebhookData: Обработанные данные webhook
        """
        pass
    
    @abstractmethod
    async def validate_webhook_signature(self, webhook_data: Dict[str, Any]) -> bool:
        """
        Валидация подписи webhook
        
        Args:
            webhook_data: Данные webhook
            
        Returns:
            bool: True если подпись валидна
        """
        pass
    
    @abstractmethod
    async def test_connection(self) -> tuple[bool, str]:
        """
        Тестирование подключения к платежной системе
        
        Returns:
            tuple[bool, str]: (успешность, сообщение)
        """
        pass
    
    def get_provider_type(self) -> PaymentProviderType:
        """Получение типа провайдера"""
        return self.provider.provider_type
    
    def get_provider_name(self) -> str:
        """Получение имени провайдера"""
        return self.provider.name
    
    def is_test_mode(self) -> bool:
        """Проверка тестового режима"""
        return self.provider.is_test_mode
    
    def get_config(self) -> Dict[str, Any]:
        """Получение конфигурации провайдера"""
        return self.provider.config or {}
    
    def get_config_value(self, key: str, default: Any = None) -> Any:
        """Получение значения из конфигурации"""
        return self.provider.get_config_value(key, default)
    
    def validate_amount(self, amount: float) -> tuple[bool, str]:
        """
        Валидация суммы платежа
        
        Args:
            amount: Сумма платежа
            
        Returns:
            tuple[bool, str]: (валидность, сообщение об ошибке)
        """
        if amount < self.provider.min_amount:
            return False, f"Сумма меньше минимальной ({self.provider.min_amount})"
        
        if self.provider.max_amount and amount > self.provider.max_amount:
            return False, f"Сумма больше максимальной ({self.provider.max_amount})"
        
        return True, ""
    
    def calculate_commission(self, amount: float) -> float:
        """
        Расчет комиссии
        
        Args:
            amount: Сумма платежа
            
        Returns:
            float: Размер комиссии
        """
        commission = self.provider.commission_fixed or 0
        commission += amount * (self.provider.commission_percent or 0) / 100
        return commission
    
    async def update_test_status(self, success: bool, message: str = None):
        """Обновление статуса тестирования"""
        status = "success" if success else "error"
        self.provider.update_test_status(status, message)
    
    async def update_payment_stats(self, amount: float, success: bool):
        """Обновление статистики платежей"""
        self.provider.update_payment_stats(amount, success)


class PaymentProcessorFactory:
    """
    Factory класс для создания процессоров платежных систем
    """
    
    _processors: Dict[PaymentProviderType, type] = {}
    
    @classmethod
    def register_processor(cls, provider_type: PaymentProviderType, processor_class: type):
        """
        Регистрация процессора для типа провайдера
        
        Args:
            provider_type: Тип провайдера
            processor_class: Класс процессора
        """
        cls._processors[provider_type] = processor_class
    
    @classmethod
    def create_processor(cls, provider: PaymentProvider) -> PaymentProcessor:
        """
        Создание процессора для провайдера
        
        Args:
            provider: Провайдер платежной системы
            
        Returns:
            PaymentProcessor: Экземпляр процессора
            
        Raises:
            ValueError: Если процессор для типа провайдера не найден
        """
        processor_class = cls._processors.get(provider.provider_type)
        if not processor_class:
            raise ValueError(f"Processor for provider type {provider.provider_type} not found")
        
        return processor_class(provider)
    
    @classmethod
    def get_supported_types(cls) -> List[PaymentProviderType]:
        """Получение списка поддерживаемых типов провайдеров"""
        return list(cls._processors.keys())
    
    @classmethod
    def is_supported(cls, provider_type: PaymentProviderType) -> bool:
        """Проверка поддержки типа провайдера"""
        return provider_type in cls._processors


class PaymentProcessorManager:
    """
    Менеджер для управления процессорами платежных систем
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self._active_processors: Dict[int, PaymentProcessor] = {}
    
    async def get_processor(self, provider: PaymentProvider) -> PaymentProcessor:
        """
        Получение процессора для провайдера
        
        Args:
            provider: Провайдер платежной системы
            
        Returns:
            PaymentProcessor: Экземпляр процессора
        """
        # Кэширование активных процессоров
        if provider.id in self._active_processors:
            return self._active_processors[provider.id]
        
        # Создание нового процессора
        processor = PaymentProcessorFactory.create_processor(provider)
        self._active_processors[provider.id] = processor
        
        return processor
    
    async def get_default_processor(self, provider_type: PaymentProviderType = None) -> Optional[PaymentProcessor]:
        """
        Получение процессора по умолчанию
        
        Args:
            provider_type: Тип провайдера (опционально)
            
        Returns:
            Optional[PaymentProcessor]: Процессор по умолчанию или None
        """
        # Здесь должна быть логика получения провайдера по умолчанию из БД
        # Пока заглушка
        return None
    
    async def test_all_processors(self) -> Dict[int, tuple[bool, str]]:
        """
        Тестирование всех активных процессоров
        
        Returns:
            Dict[int, tuple[bool, str]]: Результаты тестирования по ID провайдера
        """
        results = {}
        
        for provider_id, processor in self._active_processors.items():
            try:
                success, message = await processor.test_connection()
                results[provider_id] = (success, message)
                await processor.update_test_status(success, message)
            except Exception as e:
                error_msg = f"Ошибка тестирования: {str(e)}"
                results[provider_id] = (False, error_msg)
                await processor.update_test_status(False, error_msg)
        
        return results
    
    def clear_cache(self):
        """Очистка кэша процессоров"""
        self._active_processors.clear()
    
    def get_cached_processors(self) -> Dict[int, PaymentProcessor]:
        """Получение кэшированных процессоров"""
        return self._active_processors.copy()


# Глобальный экземпляр менеджера
payment_processor_manager = PaymentProcessorManager() 