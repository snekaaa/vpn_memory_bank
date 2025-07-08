"""
FreeKassa Payment Service Implementation
Реализация платежного сервиса FreeKassa с использованием Factory Pattern
"""
import hashlib
import hmac
import json
import asyncio
from decimal import Decimal
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timezone
import httpx
import structlog
import urllib.parse

from services.payment_processor_base import PaymentProcessorBase
from services.freekassa_config import FreeKassaConfig, FreeKassaPaymentRequest, FreeKassaWebhookData

logger = structlog.get_logger(__name__)


class FreeKassaService(PaymentProcessorBase):
    """
    Сервис для работы с FreeKassa платежной системой
    
    Реализует Factory Pattern для универсального платежного процессора
    """
    
    def __init__(self, provider_config: Dict[str, Any]):
        """
        Инициализация сервиса FreeKassa
        
        Args:
            provider_config: Конфигурация провайдера из БД
        """
        super().__init__(provider_config)
        
        # Создание типизированной конфигурации FreeKassa
        self.config = FreeKassaConfig.from_dict(provider_config)
        
        logger.info("FreeKassa service initialized", 
                   merchant_id=self.config.merchant_id,
                   test_mode=self.config.test_mode)
    
    def create_payment_url(
        self, 
        amount: float,
        order_id: str, 
        description: str,
        email: Optional[str] = None,
        success_url: Optional[str] = None,
        failure_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Создание URL для оплаты (синхронная версия)"""
        logger.info("🎯 FreeKassaService.create_payment_url called", 
                   amount=amount, order_id=order_id, description=description)
        try:
            # Создание запроса на платеж
            payment_request = FreeKassaPaymentRequest(
                amount=Decimal(str(amount)),
                order_id=order_id,
                description=description,
                currency='RUB',
                success_url=success_url or self.config.success_url,
                failure_url=failure_url or self.config.failure_url,
                notification_url=self.config.notification_url,
                customer_email=email,
                customer_phone=None
            )
            
            # Валидация запроса
            payment_request.validate(self.config)
            
            # Формирование параметров согласно документации FreeKassa
            params = {
                'm': self.config.merchant_id,     # Merchant ID (числовой)
                'oa': str(amount),               # Order Amount
                'o': order_id,                   # Order ID
                'currency': payment_request.currency,
            }
            
            # Добавление опциональных параметров в соответствии с документацией
            if payment_request.customer_email:
                params['em'] = payment_request.customer_email
            
            # Генерация подписи согласно документации FreeKassa
            signature = self._generate_payment_signature(params)
            params['s'] = signature
            
            # Базовый URL FreeKassa
            base_url = "https://pay.fk.money/"
            
            # Формирование query string с правильным URL encoding
            query_params = []
            for key, value in params.items():
                encoded_value = urllib.parse.quote(str(value), safe='')
                query_params.append(f"{key}={encoded_value}")
            
            query_string = "&".join(query_params)
            payment_url = f"{base_url}?{query_string}"
            
            logger.info("🎉 FreeKassa Payment URL created successfully", 
                       order_id=order_id, amount=amount, 
                       merchant_id=self.config.merchant_id,
                       test_mode=self.config.test_mode)
            
            return {'url': payment_url}
            
        except Exception as e:
            logger.error("Failed to create payment URL", error=str(e), order_id=order_id, amount=amount)
            raise Exception(f"Ошибка создания платежного URL: {str(e)}")
    
    async def create_payment_url_async(self, amount: Decimal, order_id: str, description: str, **kwargs) -> Dict[str, Any]:
        """
        Создание URL для оплаты через FreeKassa
        
        Args:
            amount: Сумма платежа
            order_id: Уникальный ID заказа
            description: Описание платежа
            **kwargs: Дополнительные параметры (customer_email, return_url и т.д.)
        
        Returns:
            Dict с URL для оплаты и дополнительной информацией
        """
        try:
            # Создание запроса на платеж
            payment_request = FreeKassaPaymentRequest(
                amount=amount,
                order_id=order_id,
                description=description,
                currency=kwargs.get('currency', 'RUB'),
                success_url=kwargs.get('success_url', self.config.success_url),
                failure_url=kwargs.get('failure_url', self.config.failure_url),
                notification_url=kwargs.get('notification_url', self.config.notification_url),
                customer_email=kwargs.get('customer_email'),
                customer_phone=kwargs.get('customer_phone')
            )
            
            # Валидация запроса
            payment_request.validate(self.config)
            
            # Расчет итоговой суммы с комиссией
            total_amount = self.config.calculate_total_amount(amount)
            
            # Формирование параметров согласно документации FreeKassa
            params = {
                'm': self.config.merchant_id,     # Merchant ID (числовой)
                'oa': str(amount),               # Order Amount
                'o': order_id,                   # Order ID
                'currency': payment_request.currency,
            }
            
            # Добавление опциональных параметров
            if payment_request.customer_email:
                params['em'] = payment_request.customer_email
            
            # Генерация подписи согласно документации FreeKassa
            signature = self._generate_payment_signature(params)
            params['s'] = signature
            
            # Базовый URL FreeKassa
            base_url = "https://pay.fk.money/"
            
            # Формирование query string с правильным URL encoding
            query_params = []
            for key, value in params.items():
                encoded_value = urllib.parse.quote(str(value), safe='')
                query_params.append(f"{key}={encoded_value}")
            
            query_string = "&".join(query_params)
            payment_url = f"{base_url}?{query_string}"
            
            result = {
                'payment_url': payment_url,
                'order_id': order_id,
                'amount': amount,
                'total_amount': total_amount,
                'commission': self.config.calculate_commission(amount),
                'currency': payment_request.currency,
                'test_mode': self.config.test_mode,
                'signature': signature
            }
            
            logger.info("Payment URL created", 
                       order_id=order_id, amount=amount, 
                       merchant_id=self.config.merchant_id,
                       test_mode=self.config.test_mode)
            
            return result
            
        except Exception as e:
            logger.error("Failed to create payment URL", error=str(e), order_id=order_id, amount=amount)
            raise Exception(f"Ошибка создания платежного URL: {str(e)}")
    
    def validate_webhook_signature(self, params: Dict[str, str]) -> bool:
        """Валидация подписи webhook уведомления"""
        return self._validate_webhook_signature(params)
    
    def parse_webhook_data(self, params: Dict[str, str]) -> Dict[str, Any]:
        """Парсинг данных webhook уведомления"""
        return {
            'order_id': params.get('MERCHANT_ORDER_ID', ''),
            'amount': Decimal(str(params.get('AMOUNT', '0'))),
            'currency': params.get('CURRENCY', 'RUB'),
            'status': params.get('STATUS', ''),
            'payment_id': params.get('intid', ''),
            'sign': params.get('SIGN', '')
        }
    
    async def validate_webhook(self, webhook_data: Dict[str, Any]) -> Tuple[bool, Optional[FreeKassaWebhookData]]:
        """
        Валидация webhook уведомления от FreeKassa
        
        Args:
            webhook_data: Сырые данные webhook
        
        Returns:
            Tuple (is_valid, parsed_data)
        """
        try:
            # Проверка обязательных полей
            required_fields = ['MERCHANT_ORDER_ID', 'AMOUNT', 'CURRENCY', 'STATUS', 'SIGN']
            for field in required_fields:
                if field not in webhook_data:
                    logger.warning("Missing required field in webhook", field=field)
                    return False, None
            
            # Валидация подписи
            if not self._validate_webhook_signature(webhook_data):
                logger.warning("Invalid webhook signature")
                return False, None
            
            # Парсинг данных
            parsed_data = FreeKassaWebhookData.from_request_data(webhook_data)
            
            logger.info("Webhook validated successfully", order_id=parsed_data.order_id)
            
            return True, parsed_data
            
        except Exception as e:
            logger.error("Failed to validate webhook", error=str(e))
            return False, None
    
    async def check_payment_status(self, order_id: str, payment_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Проверка статуса платежа через API FreeKassa
        
        Args:
            order_id: ID заказа для проверки
            payment_id: ID платежа (опционально)
        
        Returns:
            Словарь с информацией о статусе платежа
        """
        try:
            # Формирование параметров запроса (правильный формат)
            params = {
                'm': self.config.merchant_id,  # Merchant ID
                'o': order_id,                 # Order ID
                'nonce': str(int(datetime.now(timezone.utc).timestamp()))
            }
            
            # Добавление payment_id если предоставлен
            if payment_id:
                params['paymentId'] = payment_id
            
            # Генерация подписи для API запроса
            signature = self._generate_api_signature(params)
            params['signature'] = signature
            
            # Выполнение запроса к API
            api_url = f"{self.config.get_base_url()}/api/v1/orders/status"
            
            async with httpx.AsyncClient() as client:
                response = await client.post(api_url, json=params)
                response.raise_for_status()
                
                result = response.json()
                
                logger.info("Payment status checked", order_id=order_id, status=result.get('status'))
                
                return {
                    'order_id': order_id,
                    'status': result.get('status', 'unknown'),
                    'amount': Decimal(str(result.get('amount', '0'))),
                    'currency': result.get('currency', 'RUB'),
                    'payment_id': result.get('paymentId'),
                    'created_at': result.get('created_at'),
                    'updated_at': result.get('updated_at'),
                    'test_mode': self.config.test_mode
                }
                
        except httpx.HTTPStatusError as e:
            logger.error("HTTP error checking payment status", 
                        error=str(e), 
                        status_code=e.response.status_code,
                        order_id=order_id)
            raise Exception(f"Ошибка HTTP при проверке статуса: {e.response.status_code}")
            
        except Exception as e:
            logger.error("Failed to check payment status", error=str(e), order_id=order_id)
            raise Exception(f"Ошибка проверки статуса платежа: {str(e)}")
    
    def _generate_payment_signature(self, params: Dict[str, Any]) -> str:
        """
        Генерация подписи для создания платежа согласно документации FreeKassa
        
        Формат подписи: shopId:amount:secret1:currency:orderId
        
        Args:
            params: Параметры платежа
        
        Returns:
            Подпись в виде MD5 строки
        """
        # Формат подписи согласно документации FreeKassa
        signature_string = (
            f"{params['m']}:"          # Merchant ID
            f"{params['oa']}:"         # Order Amount  
            f"{self.config.secret1}:"  # Secret1
            f"{params['currency']}:"   # Currency
            f"{params['o']}"           # Order ID
        )
        
        logger.debug("FreeKassa signature string", signature_string=signature_string)
        
        return hashlib.md5(signature_string.encode('utf-8')).hexdigest()
    
    def _validate_webhook_signature(self, webhook_data: Dict[str, Any]) -> bool:
        """
        Валидация подписи webhook уведомления
        
        Формат подписи: merchant_id:amount:secret2:order_id
        
        Args:
            webhook_data: Данные webhook
        
        Returns:
            True если подпись валидна
        """
        try:
            received_sign = webhook_data.get('SIGN', '')
            
            # Формирование строки для проверки подписи согласно документации
            signature_string = (
                f"{webhook_data.get('MERCHANT_ID', '')}:"
                f"{webhook_data.get('AMOUNT', '')}:"
                f"{self.config.secret2}:"
                f"{webhook_data.get('MERCHANT_ORDER_ID', '')}"
            )
            
            expected_sign = hashlib.md5(signature_string.encode('utf-8')).hexdigest()
            
            logger.debug("Webhook signature validation", 
                        signature_string=signature_string,
                        expected=expected_sign,
                        received=received_sign)
            
            return hmac.compare_digest(received_sign.lower(), expected_sign.lower())
            
        except Exception as e:
            logger.error("Error validating webhook signature", error=str(e))
            return False
    
    def _generate_api_signature(self, params: Dict[str, Any]) -> str:
        """
        Генерация подписи для API запросов
        
        Args:
            params: Параметры API запроса
        
        Returns:
            Подпись в виде строки
        """
        # Создание строки для подписи (исключая signature)
        sorted_params = sorted((k, v) for k, v in params.items() if k != 'signature')
        query_string = '&'.join([f"{k}={v}" for k, v in sorted_params])
        
        # Добавление секретного ключа
        signature_string = f"{query_string}&{self.config.secret1}"
        
        return hashlib.sha256(signature_string.encode('utf-8')).hexdigest()
    
    async def handle_successful_payment(self, webhook_data: FreeKassaWebhookData) -> Dict[str, Any]:
        """
        Обработка успешного платежа
        
        Args:
            webhook_data: Данные о платеже
        
        Returns:
            Результат обработки
        """
        try:
            logger.info("Processing successful payment", 
                       order_id=webhook_data.order_id,
                       amount=webhook_data.amount,
                       payment_id=webhook_data.payment_id)
            
            # Здесь будет логика обработки успешного платежа
            # (обновление статуса подписки, активация VPN ключей и т.д.)
            
            return {
                'status': 'success',
                'order_id': webhook_data.order_id,
                'amount': webhook_data.amount,
                'payment_id': webhook_data.payment_id,
                'processed_at': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error("Failed to handle successful payment", 
                        error=str(e), 
                        order_id=webhook_data.order_id)
            raise Exception(f"Ошибка обработки успешного платежа: {str(e)}")
    
    async def handle_failed_payment(self, webhook_data: FreeKassaWebhookData) -> Dict[str, Any]:
        """
        Обработка неудачного платежа
        
        Args:
            webhook_data: Данные о платеже
        
        Returns:
            Результат обработки
        """
        try:
            logger.info("Processing failed payment", 
                       order_id=webhook_data.order_id,
                       amount=webhook_data.amount)
            
            # Здесь будет логика обработки неудачного платежа
            # (отметка о неудаче, уведомления и т.д.)
            
            return {
                'status': 'failed',
                'order_id': webhook_data.order_id,
                'amount': webhook_data.amount,
                'processed_at': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error("Failed to handle failed payment", 
                        error=str(e), 
                        order_id=webhook_data.order_id)
            raise Exception(f"Ошибка обработки неудачного платежа: {str(e)}")
    
    def get_supported_currencies(self) -> list[str]:
        """Получение списка поддерживаемых валют"""
        return ['RUB', 'USD', 'EUR', 'UAH', 'KZT']
    
    def get_commission_info(self, amount: Decimal) -> Dict[str, Any]:
        """Получение информации о комиссии"""
        commission = self.config.calculate_commission(amount)
        total = self.config.calculate_total_amount(amount)
        
        return {
            'amount': amount,
            'commission': commission,
            'commission_percent': self.config.commission_percent,
            'commission_fixed': self.config.commission_fixed,
            'total_amount': total
        } 