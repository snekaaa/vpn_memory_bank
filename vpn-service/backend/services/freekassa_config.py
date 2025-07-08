"""
FreeKassa Configuration Classes
Реализация Hybrid Approach для типобезопасной конфигурации FreeKassa
"""
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from decimal import Decimal
import json


@dataclass
class FreeKassaConfig:
    """
    Конфигурация для FreeKassa платежной системы
    
    Hybrid Approach: Type-safe dataclass с JSON validation
    Используется для валидации и работы с настройками FreeKassa
    """
    # Основные учетные данные
    merchant_id: str  # Числовой ID магазина в FreeKassa
    api_key: str
    secret1: str  # Секретное слово №1 (для формирования подписи)
    secret2: str  # Секретное слово №2 (для проверки уведомлений)
    
    # Режим работы
    test_mode: bool = True
    confirmation_mode: bool = True  # Требовать подтверждение платежа
    
    # URL конфигурация
    success_url: Optional[str] = None
    failure_url: Optional[str] = None  
    notification_url: Optional[str] = None
    notification_method: str = "POST"  # GET или POST
    
    # Лимиты платежей
    min_amount: Decimal = field(default_factory=lambda: Decimal("1.00"))
    max_amount: Decimal = field(default_factory=lambda: Decimal("100000.00"))
    
    # Комиссии
    commission_percent: Decimal = field(default_factory=lambda: Decimal("0.00"))
    commission_fixed: Decimal = field(default_factory=lambda: Decimal("0.00"))
    
    def __post_init__(self):
        """Валидация после инициализации"""
        self.validate()
    
    def validate(self) -> None:
        """Валидация конфигурации"""
        if not self.merchant_id:
            raise ValueError("Merchant ID обязателен")
            
        if not self.api_key:
            raise ValueError("API ключ обязателен")
        
        if not self.secret1:
            raise ValueError("Секретное слово №1 обязательно")
            
        if not self.secret2:
            raise ValueError("Секретное слово №2 обязательно")
        
        if self.notification_method not in ["GET", "POST"]:
            raise ValueError("Метод уведомления должен быть GET или POST")
        
        if self.min_amount < 0:
            raise ValueError("Минимальная сумма не может быть отрицательной")
            
        if self.max_amount <= self.min_amount:
            raise ValueError("Максимальная сумма должна быть больше минимальной")
        
        if self.commission_percent < 0:
            raise ValueError("Процент комиссии не может быть отрицательным")
            
        if self.commission_fixed < 0:
            raise ValueError("Фиксированная комиссия не может быть отрицательной")
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'FreeKassaConfig':
        """Создание из словаря с конвертацией типов"""
        # Конвертация Decimal полей
        if 'min_amount' in config_dict:
            config_dict['min_amount'] = Decimal(str(config_dict['min_amount']))
        if 'max_amount' in config_dict:
            config_dict['max_amount'] = Decimal(str(config_dict['max_amount']))
        if 'commission_percent' in config_dict:
            config_dict['commission_percent'] = Decimal(str(config_dict['commission_percent']))
        if 'commission_fixed' in config_dict:
            config_dict['commission_fixed'] = Decimal(str(config_dict['commission_fixed']))
        
        return cls(**config_dict)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'FreeKassaConfig':
        """Создание из JSON строки"""
        config_dict = json.loads(json_str)
        return cls.from_dict(config_dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Конвертация в словарь"""
        result = {}
        for key, value in self.__dict__.items():
            if isinstance(value, Decimal):
                result[key] = float(value)
            else:
                result[key] = value
        return result
    
    def to_json(self) -> str:
        """Конвертация в JSON"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
    
    def mask_sensitive(self) -> Dict[str, Any]:
        """Получение конфигурации с замаскированными чувствительными данными"""
        config = self.to_dict()
        
        # Маскировка чувствительных полей
        for field in ['api_key', 'secret1', 'secret2']:
            if field in config and config[field]:
                value = str(config[field])
                if len(value) > 6:
                    config[field] = "••••••" + value[-4:]
                else:
                    config[field] = "••••••"
        
        return config
    
    def get_base_url(self) -> str:
        """Получение базового URL для FreeKassa"""
        if self.test_mode:
            return "https://api.freekassa.ru"
        return "https://api.freekassa.ru"
    
    def get_payment_url(self) -> str:
        """Получение URL для создания платежа"""
        return f"{self.get_base_url()}/v1/orders/create"
    
    def calculate_commission(self, amount: Decimal) -> Decimal:
        """Расчет комиссии для суммы"""
        percent_commission = amount * (self.commission_percent / 100)
        return percent_commission + self.commission_fixed
    
    def calculate_total_amount(self, amount: Decimal) -> Decimal:
        """Расчет итоговой суммы с учетом комиссии"""
        return amount + self.calculate_commission(amount)


@dataclass
class FreeKassaPaymentRequest:
    """
    Запрос на создание платежа FreeKassa
    """
    amount: Decimal
    order_id: str
    description: str
    currency: str = "RUB"
    
    # Опциональные параметры
    success_url: Optional[str] = None
    failure_url: Optional[str] = None
    notification_url: Optional[str] = None
    
    # Дополнительные данные
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None
    
    def validate(self, config: FreeKassaConfig) -> None:
        """Валидация запроса против конфигурации"""
        if self.amount < config.min_amount:
            raise ValueError(f"Сумма {self.amount} меньше минимальной {config.min_amount}")
        
        if self.amount > config.max_amount:
            raise ValueError(f"Сумма {self.amount} больше максимальной {config.max_amount}")
        
        if not self.order_id:
            raise ValueError("ID заказа обязателен")
        
        if not self.description:
            raise ValueError("Описание платежа обязательно")


@dataclass 
class FreeKassaWebhookData:
    """
    Данные webhook уведомления от FreeKassa
    """
    order_id: str
    amount: Decimal
    currency: str
    status: str
    payment_id: str
    sign: str
    
    # Дополнительные поля
    commission: Optional[Decimal] = None
    payment_method: Optional[str] = None
    created_at: Optional[str] = None
    
    @classmethod
    def from_request_data(cls, data: Dict[str, Any]) -> 'FreeKassaWebhookData':
        """Создание из данных HTTP запроса"""
        return cls(
            order_id=data.get('MERCHANT_ORDER_ID', ''),
            amount=Decimal(str(data.get('AMOUNT', '0'))),
            currency=data.get('CURRENCY', 'RUB'),
            status=data.get('STATUS', ''),
            payment_id=data.get('intid', ''),
            sign=data.get('SIGN', ''),
            commission=Decimal(str(data.get('commission', '0'))) if data.get('commission') else None,
            payment_method=data.get('payment_method'),
            created_at=data.get('created_at')
        ) 