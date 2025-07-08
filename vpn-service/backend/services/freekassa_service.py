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
        
        logger.info("FreeKassa service initialized", test_mode=self.config.test_mode)
    
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
            
            # Формирование параметров для API FreeKassa (правильный формат согласно документации)
            params = {
                'm': self.config.api_key,  # Merchant ID
                'oa': str(amount),         # Order Amount
                'o': order_id,             # Order ID
                'us_desc': description,    # Description
                'currency': payment_request.currency,
            }
            
            # Добавление опциональных параметров
            if payment_request.customer_email:
                params['us_email'] = payment_request.customer_email
            
            if payment_request.success_url:
                params['us_success'] = payment_request.success_url
                
            if payment_request.failure_url:
                params['us_fail'] = payment_request.failure_url
                
            if payment_request.notification_url:
                params['us_notification'] = payment_request.notification_url
            
            # Генерация подписи (по правильному алгоритму FreeKassa)
            signature = self._generate_payment_signature(params)
            params['s'] = signature
            
            # Формирование URL для оплаты (правильный базовый URL из документации)
            if self.config.test_mode:
                base_url = "https://pay.fk.money/"  # Тестовый URL
            else:
                base_url = "https://pay.fk.money/"  # Продакшн URL
            
            # Создание query string
            query_params = "&".join([f"{k}={v}" for k, v in params.items()])
            payment_url = f"{base_url}?{query_params}"
            
            logger.info("🎉 FreeKassa Payment URL created successfully", 
                       order_id=order_id, amount=amount, test_mode=self.config.test_mode,
                       url_domain=payment_url.split('?')[0] if '?' in payment_url else payment_url)
            
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
            
            # Формирование параметров для API FreeKassa (правильный формат согласно документации)
            params = {
                'm': self.config.api_key,  # Merchant ID
                'oa': str(amount),         # Order Amount
                'o': order_id,             # Order ID
                'us_desc': description,    # Description
                'currency': payment_request.currency,
            }
            
            # Добавление опциональных параметров
            if payment_request.customer_email:
                params['us_email'] = payment_request.customer_email
            
            if payment_request.success_url:
                params['us_success'] = payment_request.success_url
                
            if payment_request.failure_url:
                params['us_fail'] = payment_request.failure_url
                
            if payment_request.notification_url:
                params['us_notification'] = payment_request.notification_url
            
            # Генерация подписи (по правильному алгоритму FreeKassa)
            signature = self._generate_payment_signature(params)
            params['s'] = signature
            
            # Формирование URL для оплаты (правильный базовый URL из документации)
            if self.config.test_mode:
                base_url = "https://pay.fk.money/"  # Тестовый URL
            else:
                base_url = "https://pay.fk.money/"  # Продакшн URL
            
            # Создание query string
            query_params = "&".join([f"{k}={v}" for k, v in params.items()])
            payment_url = f"{base_url}?{query_params}"
            
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
            
            logger.info("Payment URL created", order_id=order_id, amount=amount, test_mode=self.config.test_mode)
            
            return result
            
        except Exception as e:
            logger.error("Failed to create payment URL", error=str(e), order_id=order_id, amount=amount)
            raise Exception(f"Ошибка создания платежного URL: {str(e)}")
    
    def validate_webhook_signature(self, params: Dict[str, str]) -> bool:
        """Валидация подписи webhook'а (базовый интерфейс)"""
        return self._validate_webhook_signature(params)
    
    def parse_webhook_data(self, params: Dict[str, str]) -> Dict[str, Any]:
        """Парсинг данных webhook'а (базовый интерфейс)"""
        webhook_data = FreeKassaWebhookData.from_request_data(params)
        return {
            'order_id': webhook_data.order_id,
            'amount': float(webhook_data.amount),
            'currency': webhook_data.currency,
            'status': webhook_data.status,
            'payment_id': webhook_data.payment_id
        }
    
    async def validate_webhook(self, webhook_data: Dict[str, Any]) -> Tuple[bool, Optional[FreeKassaWebhookData]]:
        """
        Валидация webhook уведомления от FreeKassa
        
        Args:
            webhook_data: Данные webhook запроса
        
        Returns:
            Tuple (is_valid: bool, parsed_data: FreeKassaWebhookData | None)
        """
        try:
            # Парсинг данных webhook
            parsed_data = FreeKassaWebhookData.from_request_data(webhook_data)
            
            # Проверка подписи
            is_signature_valid = self._validate_webhook_signature(webhook_data)
            
            if not is_signature_valid:
                logger.warning("Invalid webhook signature", order_id=parsed_data.order_id)
                return False, None
            
            # Дополнительные проверки
            if not parsed_data.order_id:
                logger.warning("Missing order_id in webhook")
                return False, None
            
            if parsed_data.amount <= 0:
                logger.warning("Invalid amount in webhook", amount=parsed_data.amount)
                return False, None
            
            logger.info("Webhook validated successfully", 
                       order_id=parsed_data.order_id, 
                       amount=parsed_data.amount,
                       status=parsed_data.status)
            
            return True, parsed_data
            
        except Exception as e:
            logger.error("Webhook validation failed", error=str(e))
            return False, None
    
    async def check_payment_status(self, order_id: str, payment_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Проверка статуса платежа через API FreeKassa
        
        Args:
            order_id: ID заказа
            payment_id: ID платежа в системе FreeKassa (опционально)
        
        Returns:
            Dict со статусом платежа
        """
        try:
            # Формирование параметров запроса (правильный формат)
            params = {
                'm': self.config.api_key,  # Merchant ID
                'o': order_id,             # Order ID
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
        Генерация подписи для создания платежа (правильный алгоритм FreeKassa)
        
        Args:
            params: Параметры платежа
        
        Returns:
            Подпись в виде строки
        """
        # Порядок параметров для подписи (согласно документации FreeKassa)
        # Формат: shopId:amount:secret1:currency:orderId
        signature_string = (
            f"{params['m']}:"      # Merchant ID (было shopId)
            f"{params['oa']}:"     # Order Amount (было sum)  
            f"{self.config.secret1}:"
            f"{params['currency']}:"
            f"{params['o']}"       # Order ID (было orderid)
        )
        
        logger.debug("FreeKassa signature string", signature_string=signature_string)
        
        return hashlib.md5(signature_string.encode('utf-8')).hexdigest()
    
    def _validate_webhook_signature(self, webhook_data: Dict[str, Any]) -> bool:
        """
        Валидация подписи webhook уведомления
        
        Args:
            webhook_data: Данные webhook
        
        Returns:
            True если подпись валидна
        """
        try:
            received_sign = webhook_data.get('SIGN', '')
            
            # Формирование строки для проверки подписи
            signature_string = (
                f"{webhook_data.get('MERCHANT_ORDER_ID', '')}:"
                f"{webhook_data.get('AMOUNT', '')}:"
                f"{self.config.secret2}"
            )
            
            expected_sign = hashlib.md5(signature_string.encode('utf-8')).hexdigest()
            
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