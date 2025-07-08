"""
Базовый абстрактный класс для платежных процессоров
Реализует Factory Pattern для универсального интерфейса
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class PaymentConfig:
    """Базовая конфигурация для всех платежных систем"""
    test_mode: bool = True
    
class PaymentProcessorBase(ABC):
    """Абстрактный базовый класс для всех платежных процессоров"""
    
    def __init__(self, provider_config: Dict[str, Any]):
        """
        Инициализация процессора
        
        Args:
            provider_config: Конфигурация провайдера из БД
        """
        if not provider_config:
            raise ValueError("Provider config is required")
        
        self.provider_config = provider_config
        self.test_mode = provider_config.get('test_mode', True)
    
    @abstractmethod
    def create_payment_url(
        self, 
        amount: float,
        order_id: str, 
        description: str,
        email: Optional[str] = None,
        success_url: Optional[str] = None,
        failure_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Создание URL для оплаты"""
        pass
    
    @abstractmethod
    def validate_webhook_signature(self, params: Dict[str, str]) -> bool:
        """Валидация подписи webhook'а"""
        pass
    
    @abstractmethod
    def parse_webhook_data(self, params: Dict[str, str]) -> Dict[str, Any]:
        """Парсинг данных webhook'а"""
        pass
    
    @abstractmethod
    async def check_payment_status(self, invoice_id: str) -> Dict[str, Any]:
        """Проверка статуса платежа"""
        pass
    
    def get_config_value(self, key: str, default: Any = None) -> Any:
        """Получение значения из конфигурации"""
        return self.provider_config.get(key, default) 