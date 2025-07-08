"""
Payment Processor Factory
Реализация Factory Pattern для создания платежных процессоров
"""
from typing import Dict, Type, Any, Optional
import structlog

from services.payment_processor_base import PaymentProcessorBase
from models.payment_provider import PaymentProvider, PaymentProviderType

logger = structlog.get_logger(__name__)


class PaymentProcessorFactory:
    """
    Фабрика для создания платежных процессоров
    
    Реализует Factory Pattern с registry для динамической регистрации провайдеров
    """
    
    # Реестр зарегистрированных процессоров
    _processors: Dict[PaymentProviderType, Type[PaymentProcessorBase]] = {}
    
    @classmethod
    def register_processor(cls, provider_type: PaymentProviderType, processor_class: Type[PaymentProcessorBase]) -> None:
        """
        Регистрация нового платежного процессора
        
        Args:
            provider_type: Тип платежного провайдера
            processor_class: Класс процессора
        """
        cls._processors[provider_type] = processor_class
        logger.info("Payment processor registered", provider_type=provider_type.value, 
                   processor_class=processor_class.__name__)
    
    @classmethod
    def create_processor(cls, provider: PaymentProvider) -> PaymentProcessorBase:
        """
        Создание экземпляра платежного процессора
        
        Args:
            provider: Экземпляр PaymentProvider из базы данных
        
        Returns:
            Экземпляр соответствующего платежного процессора
        
        Raises:
            ValueError: Если процессор для данного типа не зарегистрирован
        """
        if provider.provider_type not in cls._processors:
            raise ValueError(f"Процессор для типа {provider.provider_type} не зарегистрирован")
        
        processor_class = cls._processors[provider.provider_type]
        
        # Подготовка конфигурации для процессора
        config = cls._prepare_config(provider)
        
        logger.info("🏭 Creating processor", 
                   provider_type=provider.provider_type.value,
                   provider_id=provider.id,
                   processor_class=processor_class.__name__,
                   config_keys=list(config.keys()))
        
        try:
            processor = processor_class(config)
            logger.info("✅ Payment processor created successfully", 
                       provider_type=provider.provider_type.value,
                       provider_id=provider.id,
                       processor_class=processor_class.__name__)
            return processor
            
        except Exception as e:
            logger.error("Failed to create payment processor", 
                        provider_type=provider.provider_type.value,
                        provider_id=provider.id,
                        error=str(e))
            raise Exception(f"Ошибка создания процессора {provider.provider_type}: {str(e)}")
    
    @classmethod
    def get_registered_processors(cls) -> Dict[PaymentProviderType, Type[PaymentProcessorBase]]:
        """Получение списка зарегистрированных процессоров"""
        return cls._processors.copy()
    
    @classmethod
    def is_processor_registered(cls, provider_type: PaymentProviderType) -> bool:
        """Проверка регистрации процессора для данного типа"""
        return provider_type in cls._processors
    
    @classmethod
    def _prepare_config(cls, provider: PaymentProvider) -> Dict[str, Any]:
        """
        Подготовка конфигурации для процессора из данных провайдера
        
        Args:
            provider: Экземпляр PaymentProvider
        
        Returns:
            Словарь конфигурации для процессора
        """
        base_config = {
            'test_mode': provider.is_test_mode,
            'min_amount': provider.min_amount,
            'max_amount': provider.max_amount,
            'commission_percent': provider.commission_percent,
            'commission_fixed': provider.commission_fixed,
            'success_url': provider.success_url,
            'failure_url': provider.failure_url,
            'notification_url': provider.notification_url,
            'notification_method': provider.notification_method,
        }
        
        # Добавление специфичной для провайдера конфигурации
        if provider.provider_type == PaymentProviderType.robokassa:
            robokassa_config = provider.get_robokassa_config()
            base_config.update(robokassa_config)
            
        elif provider.provider_type == PaymentProviderType.freekassa:
            freekassa_config = provider.get_freekassa_config()
            base_config.update(freekassa_config)
            
        elif provider.provider_type == PaymentProviderType.yookassa:
            yookassa_config = provider.get_yookassa_config()
            base_config.update(yookassa_config)
        
        return base_config


def register_all_processors() -> None:
    """
    Регистрация всех доступных платежных процессоров
    """
    try:
        # Регистрация Robokassa
        try:
            from services.robokassa_service import RobokassaService
            PaymentProcessorFactory.register_processor(PaymentProviderType.robokassa, RobokassaService)
        except ImportError:
            logger.warning("RobokassaService not available for registration")
        
        # Регистрация FreeKassa
        try:
            from services.freekassa_service import FreeKassaService
            PaymentProcessorFactory.register_processor(PaymentProviderType.freekassa, FreeKassaService)
        except ImportError:
            logger.warning("FreeKassaService not available for registration")
        
        # Регистрация YooKassa
        try:
            from services.yookassa_service import YooKassaService
            PaymentProcessorFactory.register_processor(PaymentProviderType.yookassa, YooKassaService)
        except ImportError:
            logger.warning("YooKassaService not available for registration")
        
        logger.info("Payment processors registration completed", 
                   registered_count=len(PaymentProcessorFactory.get_registered_processors()))
        
    except Exception as e:
        logger.error("Failed to register payment processors", error=str(e))
        raise


# Автоматическая регистрация процессоров при импорте модуля
register_all_processors() 