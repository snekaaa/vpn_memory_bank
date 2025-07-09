"""
Сервис для работы с Робокассой
Реализует создание платежей, проверку подписей и статусов
"""

import hashlib
import hmac
import logging
from typing import Dict, Optional, Any
from urllib.parse import urlencode, urlparse, parse_qs
import aiohttp
import asyncio
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class RobokassaService:
    """Сервис для работы с API Робокассы"""
    
    def __init__(self, provider_config: Dict[str, Any]):
        """
        Инициализация сервиса Робокассы
        
        Args:
            provider_config: Конфигурация провайдера из БД (обязательно)
        """
        if not provider_config:
            raise ValueError("Provider config is required for RobokassaService")
        
        # Используем конфигурацию провайдера из БД
        logger.info("Using Robokassa config from payment provider")
        self.shop_id = provider_config.get('shop_id')
        self.password1 = provider_config.get('password1') 
        self.password2 = provider_config.get('password2')
        self.base_url = provider_config.get('base_url', 'https://auth.robokassa.ru/Merchant/Index.aspx')
        self.test_mode = provider_config.get('test_mode', False)
        
        # Проверяем конфигурацию
        if not all([self.shop_id, self.password1, self.password2]):
            logger.error("Robokassa configuration incomplete")
            raise ValueError("Incomplete Robokassa configuration: shop_id, password1, and password2 are required")
        else:
            logger.info(f"Robokassa service initialized for shop_id: {self.shop_id}")
    
    def _generate_signature(self, params: Dict[str, Any], password: str) -> str:
        """
        Генерация подписи для Робокассы по стандартному алгоритму
        
        Args:
            params: Параметры для подписи
            password: Пароль для подписи
            
        Returns:
            Хеш подписи
        """
        # Для стандартного алгоритма Робокассы используем конкретный порядок параметров
        # Для платежа: MerchantLogin:OutSum:InvId:Password
        # Для результата: OutSum:InvId:Password
        
        if 'MerchantLogin' in params:
            # Для создания платежа
            signature_string = f"{params['MerchantLogin']}:{params['OutSum']}:{params['InvId']}:{password}"
        else:
            # Для проверки результата и success URL
            signature_string = f"{params['OutSum']}:{params['InvId']}:{password}"
        
        # Логируем для отладки (маскируем пароль)
        masked_string = signature_string.replace(password, "***")
        logger.info(f"Signature string (masked): {masked_string}")
        
        # Создаем MD5 хеш
        signature = hashlib.md5(signature_string.encode('utf-8')).hexdigest()
        logger.info(f"Generated signature: {signature}")
        
        return signature
    
    def create_payment_url(
        self, 
        amount: float, 
        order_id: str, 
        description: str,
        email: Optional[str] = None,
        success_url: Optional[str] = None,
        failure_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Создание URL для оплаты в Робокассе
        
        Args:
            amount: Сумма платежа
            order_id: Уникальный ID заказа
            description: Описание платежа
            email: Email пользователя (опционально)
            success_url: URL успешной оплаты
            failure_url: URL неуспешной оплаты
            
        Returns:
            Dict с URL для перенаправления на оплату
        """
        params = {
            'MerchantLogin': self.shop_id,
            'OutSum': str(amount),
            'InvId': order_id,
            'Description': description,
            'IsTest': '1' if self.test_mode else '0'
        }
        
        # Добавляем опциональные параметры
        if email:
            params['Email'] = email
        if success_url:
            params['SuccessURL'] = success_url
        if failure_url:
            params['FailURL'] = failure_url
        
        # Генерируем подпись
        signature_params = {
            'MerchantLogin': self.shop_id,
            'OutSum': str(amount),
            'InvId': order_id
        }
        
        signature = self._generate_signature(signature_params, self.password1)
        params['SignatureValue'] = signature
        
        # Формируем URL
        query_string = urlencode(params, quote_via=lambda x, *args: x)
        payment_url = f"{self.base_url}?{query_string}"
        
        logger.info(f"🔴 RobokassaService created payment URL for order {order_id}, amount {amount}")
        return {'url': payment_url}
    
    def validate_result_signature(self, params: Dict[str, str]) -> bool:
        """
        Проверка подписи ResultURL (уведомление об оплате)
        
        Args:
            params: Параметры от Робокассы
            
        Returns:
            True если подпись валидна
        """
        try:
            # Получаем подпись из параметров
            received_signature = params.get('SignatureValue', '').lower()
            
            # Параметры для проверки подписи (без MerchantLogin для результата)
            signature_params = {
                'OutSum': params.get('OutSum'),
                'InvId': params.get('InvId')
            }
            
            # Генерируем ожидаемую подпись
            expected_signature = self._generate_signature(signature_params, self.password2)
            
            # Сравниваем подписи
            is_valid = hmac.compare_digest(received_signature, expected_signature.lower())
            
            if not is_valid:
                logger.warning(f"Invalid signature for invoice {params.get('InvId')}")
            
            return is_valid
            
        except Exception as e:
            logger.error(f"Error validating signature: {e}")
            return False
    
    def validate_success_signature(self, params: Dict[str, str]) -> bool:
        """
        Проверка подписи SuccessURL (страница успешной оплаты)
        
        Для SuccessURL Робокасса использует password1, а не password2
        
        Args:
            params: Параметры от Робокассы
            
        Returns:
            True если подпись валидна
        """
        try:
            # Получаем подпись из параметров
            received_signature = params.get('SignatureValue', '').lower()
            
            # Параметры для проверки подписи (без MerchantLogin)
            signature_params = {
                'OutSum': params.get('OutSum'),
                'InvId': params.get('InvId')
            }
            
            logger.info(f"🔍 SUCCESS SIGNATURE DEBUG:")
            logger.info(f"  - OutSum: {params.get('OutSum')}")
            logger.info(f"  - InvId: {params.get('InvId')}")
            logger.info(f"  - Received signature: {received_signature}")
            logger.info(f"  - Shop ID: {self.shop_id}")
            logger.info(f"  - Using password1 (length: {len(self.password1) if self.password1 else 0})")
            
            # Генерируем ожидаемую подпись с password1 (не password2!)
            expected_signature = self._generate_signature(signature_params, self.password1)
            
            # Сравниваем подписи
            is_valid = hmac.compare_digest(received_signature, expected_signature.lower())
            
            logger.info(f"  - Expected signature: {expected_signature.lower()}")
            logger.info(f"  - Signatures match: {is_valid}")
            
            if not is_valid:
                logger.error(f"❌ Invalid success signature for invoice {params.get('InvId')}")
                logger.error(f"   Received: {received_signature}")
                logger.error(f"   Expected: {expected_signature.lower()}")
            
            return is_valid
            
        except Exception as e:
            logger.error(f"Error validating success signature: {e}")
            return False
    
    async def check_payment_status(self, invoice_id: str) -> Dict[str, Any]:
        """
        Проверка статуса платежа через API Робокассы
        
        Args:
            invoice_id: ID инвойса
            
        Returns:
            Словарь с информацией о платеже
        """
        try:
            # URL для проверки статуса
            check_url = "https://auth.robokassa.ru/Merchant/WebService/Service.asmx/OpState"
            
            # Параметры для проверки
            params = {
                'MerchantLogin': self.shop_id,
                'InvoiceID': invoice_id
            }
            
            # Генерируем подпись
            signature = self._generate_signature(params, self.password2)
            params['Signature'] = signature
            
            # Выполняем запрос
            async with aiohttp.ClientSession() as session:
                async with session.post(check_url, data=params) as response:
                    if response.status == 200:
                        result = await response.text()
                        
                        # Простой парсинг XML ответа
                        if "StateCode:100" in result:
                            return {
                                'status': 'paid',
                                'message': 'Payment completed successfully'
                            }
                        elif "StateCode:50" in result:
                            return {
                                'status': 'pending',
                                'message': 'Payment is being processed'
                            }
                        else:
                            return {
                                'status': 'unknown',
                                'message': 'Unknown payment status'
                            }
                    else:
                        logger.error(f"Error checking payment status: {response.status}")
                        return {
                            'status': 'error',
                            'message': f'API error: {response.status}'
                        }
                        
        except Exception as e:
            logger.error(f"Error checking payment status: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def parse_webhook_data(self, params: Dict[str, str]) -> Dict[str, Any]:
        """
        Парсинг данных от webhook Робокассы
        
        Args:
            params: Параметры от Робокассы
            
        Returns:
            Обработанные данные платежа
        """
        return {
            'invoice_id': params.get('InvId'),
            'amount': float(params.get('OutSum', 0)),
            'payment_method': params.get('PaymentMethod'),
            'signature': params.get('SignatureValue'),
            'fee': float(params.get('Fee', 0)),
            'email': params.get('EMail'),
            'currency': params.get('IncCurrLabel', 'RUB'),
            'payment_date': datetime.now(timezone.utc),
            'raw_data': params
        }
    
    def get_subscription_plans(self) -> Dict[str, Dict[str, Any]]:
        """
        Получение доступных тарифных планов
        
        Returns:
            Словарь с тарифными планами
        """
        from services.service_plans_manager import service_plans_manager
        return service_plans_manager.get_plans_for_robokassa() 