"""
Улучшенные утилиты для VPN Memory Bank
Рефакторинг старых методов из main.py
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import re
from decimal import Decimal


class SubscriptionType(Enum):
    """Типы подписок с их характеристиками"""
    WEEKLY = ("weekly", Decimal("200.00"), 7)
    MONTHLY = ("monthly", Decimal("500.00"), 30)
    QUARTERLY = ("quarterly", Decimal("1200.00"), 90)
    YEARLY = ("yearly", Decimal("4000.00"), 365)
    
    def __init__(self, type_name: str, price: Decimal, days: int):
        self.type_name = type_name
        self.price = price
        self.days = days


class PaymentProvider(Enum):
    """Провайдеры платежей с их характеристиками"""
    ROBOKASSA = ("robokassa", "https://robokassa.ru", True)
    FREEKASSA = ("freekassa", "https://freekassa.ru", False)
    YOOKASSA = ("yookassa", "https://yookassa.ru", True)
    COINGATE = ("coingate", "https://coingate.com", False)
    
    def __init__(self, provider_name: str, base_url: str, supports_autopay: bool):
        self.provider_name = provider_name
        self.base_url = base_url
        self.supports_autopay = supports_autopay


@dataclass
class ValidationError:
    """Класс для представления ошибки валидации"""
    field: str
    message: str
    code: str


class PaymentValidator:
    """
    Улучшенный валидатор платежных данных
    Заменяет старый метод validate_payment_data
    """
    
    EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    
    @classmethod
    def validate_payment_data(cls, payment_data: Dict[str, Any]) -> Tuple[bool, List[ValidationError]]:
        """
        Валидация данных платежа с улучшенной структурой
        
        Args:
            payment_data: Данные для валидации
            
        Returns:
            Tuple[bool, List[ValidationError]]: (is_valid, errors)
        """
        errors: List[ValidationError] = []
        
        # Валидация user_id
        errors.extend(cls._validate_user_id(payment_data.get("user_id")))
        
        # Валидация subscription_type
        errors.extend(cls._validate_subscription_type(payment_data.get("subscription_type")))
        
        # Валидация provider_type
        errors.extend(cls._validate_provider_type(payment_data.get("provider_type")))
        
        # Валидация email (опционально)
        if payment_data.get("user_email"):
            errors.extend(cls._validate_email(payment_data["user_email"]))
        
        # Валидация автоплатежа
        errors.extend(cls._validate_autopay(
            payment_data.get("enable_autopay"),
            payment_data.get("provider_type")
        ))
        
        return len(errors) == 0, errors
    
    @classmethod
    def _validate_user_id(cls, user_id: Any) -> List[ValidationError]:
        """Валидация user_id"""
        errors = []
        
        if user_id is None:
            errors.append(ValidationError("user_id", "User ID is required", "REQUIRED"))
        elif not isinstance(user_id, int):
            errors.append(ValidationError("user_id", "User ID must be an integer", "INVALID_TYPE"))
        elif user_id <= 0:
            errors.append(ValidationError("user_id", "User ID must be positive", "INVALID_VALUE"))
        
        return errors
    
    @classmethod
    def _validate_subscription_type(cls, subscription_type: Any) -> List[ValidationError]:
        """Валидация типа подписки"""
        errors = []
        
        if subscription_type is None:
            errors.append(ValidationError("subscription_type", "Subscription type is required", "REQUIRED"))
        elif not isinstance(subscription_type, str):
            errors.append(ValidationError("subscription_type", "Subscription type must be a string", "INVALID_TYPE"))
        else:
            valid_types = [sub_type.type_name for sub_type in SubscriptionType]
            if subscription_type not in valid_types:
                errors.append(ValidationError(
                    "subscription_type", 
                    f"Invalid subscription type. Must be one of: {', '.join(valid_types)}", 
                    "INVALID_VALUE"
                ))
        
        return errors
    
    @classmethod
    def _validate_provider_type(cls, provider_type: Any) -> List[ValidationError]:
        """Валидация типа провайдера"""
        errors = []
        
        if provider_type is None:
            errors.append(ValidationError("provider_type", "Provider type is required", "REQUIRED"))
        elif not isinstance(provider_type, str):
            errors.append(ValidationError("provider_type", "Provider type must be a string", "INVALID_TYPE"))
        else:
            valid_providers = [provider.provider_name for provider in PaymentProvider]
            if provider_type not in valid_providers:
                errors.append(ValidationError(
                    "provider_type",
                    f"Invalid provider type. Must be one of: {', '.join(valid_providers)}",
                    "INVALID_VALUE"
                ))
        
        return errors
    
    @classmethod
    def _validate_email(cls, email: str) -> List[ValidationError]:
        """Валидация email адреса"""
        errors = []
        
        if not isinstance(email, str):
            errors.append(ValidationError("user_email", "Email must be a string", "INVALID_TYPE"))
        elif len(email) < 5:
            errors.append(ValidationError("user_email", "Email is too short", "INVALID_LENGTH"))
        elif not cls.EMAIL_PATTERN.match(email):
            errors.append(ValidationError("user_email", "Invalid email format", "INVALID_FORMAT"))
        
        return errors
    
    @classmethod
    def _validate_autopay(cls, enable_autopay: Any, provider_type: Optional[str]) -> List[ValidationError]:
        """Валидация настроек автоплатежа"""
        errors = []
        
        if enable_autopay is not None:
            if not isinstance(enable_autopay, bool):
                errors.append(ValidationError("enable_autopay", "Autopay must be boolean", "INVALID_TYPE"))
            elif enable_autopay and provider_type:
                # Проверяем поддержку автоплатежей провайдером
                provider_found = None
                for provider in PaymentProvider:
                    if provider.provider_name == provider_type:
                        provider_found = provider
                        break
                
                if provider_found and not provider_found.supports_autopay:
                        errors.append(ValidationError(
                            "enable_autopay",
                            f"Provider {provider_type} does not support autopay",
                            "FEATURE_NOT_SUPPORTED"
                        ))
        
        return errors


class PaymentCalculator:
    """
    Улучшенный калькулятор платежей
    Заменяет старый метод calculate_payment_amount
    """
    
    @staticmethod
    def calculate_amount(subscription_type: str) -> Decimal:
        """
        Рассчитывает сумму платежа для типа подписки
        
        Args:
            subscription_type: Тип подписки
            
        Returns:
            Decimal: Сумма платежа
            
        Raises:
            ValueError: Если тип подписки неизвестен
        """
        for subscription in SubscriptionType:
            if subscription.type_name == subscription_type:
                return subscription.price
        raise ValueError(f"Unknown subscription type: {subscription_type}")
    
    @staticmethod
    def get_subscription_info(subscription_type: str) -> Dict[str, Any]:
        """
        Получает полную информацию о подписке
        
        Args:
            subscription_type: Тип подписки
            
        Returns:
            Dict с информацией о подписке
        """
        for subscription in SubscriptionType:
            if subscription.type_name == subscription_type:
                return {
                    "type": subscription.type_name,
                    "price": float(subscription.price),
                    "days": subscription.days,
                    "currency": "RUB"
                }
        raise ValueError(f"Unknown subscription type: {subscription_type}")


class PaymentUrlGenerator:
    """
    Улучшенный генератор URL платежей
    Заменяет старый метод generate_payment_url
    """
    
    # Конфигурация провайдеров (в реальном приложении из настроек)
    PROVIDER_CONFIG = {
        "robokassa": {
            "merchant_login": "vpn-bezlagov",
            "test_mode": True
        },
        "freekassa": {
            "merchant_id": "12345",
            "secret_key": "secret_key_here"
        },
        "yookassa": {
            "shop_id": "shop_id_here"
        },
        "coingate": {
            "api_key": "api_key_here"
        }
    }
    
    @classmethod
    def generate_url(cls, provider: str, payment_id: int, amount: Decimal, **kwargs) -> str:
        """
        Генерирует URL для платежа
        
        Args:
            provider: Провайдер платежей
            payment_id: ID платежа
            amount: Сумма платежа
            **kwargs: Дополнительные параметры
            
        Returns:
            str: URL для оплаты
            
        Raises:
            ValueError: Если провайдер неизвестен
        """
        # Проверяем что провайдер существует
        provider_found = None
        for payment_provider in PaymentProvider:
            if payment_provider.provider_name == provider:
                provider_found = payment_provider
                break
        
        if not provider_found:
            raise ValueError(f"Unknown payment provider: {provider}")
        
        try:
            generator_method = getattr(cls, f'_generate_{provider}_url')
            return generator_method(payment_id, amount, **kwargs)
        except AttributeError:
            raise ValueError(f"Unknown payment provider: {provider}")
    
    @classmethod
    def _generate_robokassa_url(cls, payment_id: int, amount: Decimal, **kwargs) -> str:
        """Генерация URL для Robokassa"""
        config = cls.PROVIDER_CONFIG["robokassa"]
        base_url = "https://robokassa.ru"
        
        params = {
            "MerchantLogin": config["merchant_login"],
            "OutSum": str(amount),
            "InvId": payment_id,
            "Description": kwargs.get("description", "VPN Subscription")
        }
        
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        return f"{base_url}/Merchant/Index.aspx?{query_string}"
    
    @classmethod
    def _generate_freekassa_url(cls, payment_id: int, amount: Decimal, **kwargs) -> str:
        """Генерация URL для FreeKassa"""
        config = cls.PROVIDER_CONFIG["freekassa"]
        base_url = "https://freekassa.ru"
        
        params = {
            "m": config["merchant_id"],
            "oa": str(amount),
            "o": payment_id,
            "s": "signature_hash"  # В реальности - вычисленная подпись
        }
        
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        return f"{base_url}/pay?{query_string}"
    
    @classmethod
    def _generate_yookassa_url(cls, payment_id: int, amount: Decimal, **kwargs) -> str:
        """Генерация URL для YooKassa"""
        base_url = "https://yookassa.ru"
        return f"{base_url}/checkout?amount={amount}&order_id={payment_id}"
    
    @classmethod
    def _generate_coingate_url(cls, payment_id: int, amount: Decimal, **kwargs) -> str:
        """Генерация URL для CoinGate"""
        base_url = "https://coingate.com"
        return f"{base_url}/invoice/create?price_amount={amount}&order_id=order_{payment_id}"


class PaymentService:
    """
    Сервис для работы с платежами
    Объединяет все улучшенные компоненты
    """
    
    def __init__(self):
        self.validator = PaymentValidator()
        self.calculator = PaymentCalculator()
        self.url_generator = PaymentUrlGenerator()
    
    def create_payment(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Создание платежа с использованием улучшенных методов
        
        Args:
            payment_data: Данные платежа
            
        Returns:
            Dict с результатом создания платежа
            
        Raises:
            ValueError: При ошибках валидации или создания
        """
        # Валидация данных
        is_valid, errors = self.validator.validate_payment_data(payment_data)
        
        if not is_valid:
            error_messages = [f"{error.field}: {error.message}" for error in errors]
            raise ValueError(f"Validation failed: {'; '.join(error_messages)}")
        
        # Расчет суммы
        try:
            amount = self.calculator.calculate_amount(payment_data["subscription_type"])
            subscription_info = self.calculator.get_subscription_info(payment_data["subscription_type"])
        except ValueError as e:
            raise ValueError(f"Amount calculation failed: {str(e)}")
        
        # Генерация ID платежа (в реальности - из БД)
        payment_id = hash(str(payment_data)) % 1000000
        
        # Генерация URL
        try:
            payment_url = self.url_generator.generate_url(
                payment_data["provider_type"],
                payment_id,
                amount,
                description=f"VPN {subscription_info['type']} subscription"
            )
        except ValueError as e:
            raise ValueError(f"URL generation failed: {str(e)}")
        
        return {
            "payment_id": payment_id,
            "amount": float(amount),
            "currency": "RUB",
            "payment_url": payment_url,
            "subscription_info": subscription_info,
            "provider": payment_data["provider_type"]
        }