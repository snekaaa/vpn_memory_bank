"""
Процессор платежей для Робокассы
Реализует PaymentProcessor для интеграции с Робокассой
"""

import hashlib
import hmac
import logging
from typing import Dict, Any, Optional
from urllib.parse import urlencode
import aiohttp
from datetime import datetime

from .payment_processor import (
    PaymentProcessor, PaymentRequest, PaymentResponse, 
    PaymentStatus, WebhookData, PaymentProcessorFactory
)
from models.payment_provider import PaymentProvider, PaymentProviderType


class RobokassaProcessor(PaymentProcessor):
    """Процессор платежей для Робокассы"""
    
    def __init__(self, provider: PaymentProvider):
        super().__init__(provider)
        
        # Валидация типа провайдера
        if provider.provider_type != PaymentProviderType.robokassa:
            raise ValueError("Provider type must be ROBOKASSA")
        
        # Получение конфигурации
        self.shop_id = self.get_config_value("shop_id")
        self.password1 = self.get_config_value("password1")
        self.password2 = self.get_config_value("password2")
        self.base_url = self.get_config_value("base_url", "https://auth.robokassa.ru/Merchant/Index.aspx")
        
        # Проверка обязательных параметров
        if not all([self.shop_id, self.password1, self.password2]):
            self.logger.warning("Robokassa configuration incomplete")
    
    def _generate_signature(self, params: Dict[str, Any], password: str) -> str:
        """
        Генерация подписи для Робокассы по стандартному алгоритму
        
        Args:
            params: Параметры для подписи
            password: Пароль для подписи
            
        Returns:
            Хеш подписи
        """
        if 'MerchantLogin' in params:
            # Для создания платежа
            signature_string = f"{params['MerchantLogin']}:{params['OutSum']}:{params['InvId']}:{password}"
        else:
            # Для проверки результата
            signature_string = f"{params['OutSum']}:{params['InvId']}:{password}"
        
        self.logger.debug(f"Signature string: {signature_string}")
        
        # Создаем MD5 хеш
        signature = hashlib.md5(signature_string.encode('utf-8')).hexdigest()
        self.logger.debug(f"Generated signature: {signature}")
        
        return signature
    
    async def create_payment(self, request: PaymentRequest) -> PaymentResponse:
        """
        Создание платежа в Робокассе
        
        Args:
            request: Запрос на создание платежа
            
        Returns:
            PaymentResponse: Ответ с данными созданного платежа
        """
        try:
            # Валидация суммы
            amount_valid, amount_error = self.validate_amount(request.amount)
            if not amount_valid:
                return PaymentResponse(
                    success=False,
                    error_message=amount_error
                )
            
            # Генерация уникального invoice_id
            invoice_id = f"{request.user_id}_{int(datetime.now().timestamp())}"
            
            # Параметры для Робокассы
            params = {
                'MerchantLogin': self.shop_id,
                'OutSum': str(request.amount),
                'InvId': invoice_id,
                'Description': request.description or f"VPN подписка для пользователя {request.user_id}",
                'IsTest': '1' if self.is_test_mode() else '0'
            }
            
            # Добавляем опциональные параметры
            if request.return_url:
                params['SuccessURL'] = request.return_url
            
            # Генерируем подпись
            signature_params = {
                'MerchantLogin': self.shop_id,
                'OutSum': str(request.amount),
                'InvId': invoice_id
            }
            
            signature = self._generate_signature(signature_params, self.password1)
            params['SignatureValue'] = signature
            
            # Формируем URL для оплаты
            query_string = urlencode(params, quote_via=lambda x, *args: x)
            payment_url = f"{self.base_url}?{query_string}"
            
            self.logger.info(f"Created Robokassa payment for user {request.user_id}, amount {request.amount}")
            
            return PaymentResponse(
                success=True,
                payment_id=invoice_id,
                confirmation_url=payment_url,
                external_payment_id=invoice_id,
                provider_data={
                    "invoice_id": invoice_id,
                    "shop_id": self.shop_id,
                    "test_mode": self.is_test_mode()
                }
            )
            
        except Exception as e:
            self.logger.error(f"Error creating Robokassa payment: {e}")
            return PaymentResponse(
                success=False,
                error_message=f"Ошибка создания платежа: {str(e)}"
            )
    
    async def check_payment_status(self, external_payment_id: str) -> PaymentStatus:
        """
        Проверка статуса платежа в Робокассе
        
        Args:
            external_payment_id: Invoice ID в Робокассе
            
        Returns:
            PaymentStatus: Статус платежа
        """
        try:
            # В текущей реализации Робокассы статус проверяется через webhook
            # Для полной реализации нужно использовать API Робокассы
            
            self.logger.info(f"Checking Robokassa payment status for invoice {external_payment_id}")
            
            # Заглушка - в реальности нужно обращаться к API Робокассы
            return PaymentStatus(
                external_payment_id=external_payment_id,
                status="pending",
                amount=0.0,
                currency="RUB"
            )
            
        except Exception as e:
            self.logger.error(f"Error checking payment status: {e}")
            return PaymentStatus(
                external_payment_id=external_payment_id,
                status="error",
                amount=0.0,
                currency="RUB",
                error_message=str(e)
            )
    
    async def process_webhook(self, webhook_data: Dict[str, Any]) -> WebhookData:
        """
        Обработка webhook уведомления от Робокассы
        
        Args:
            webhook_data: Данные webhook от Робокассы
            
        Returns:
            WebhookData: Обработанные данные webhook
        """
        try:
            # Получаем данные из webhook
            external_payment_id = webhook_data.get('InvId')
            amount = float(webhook_data.get('OutSum', 0))
            
            # Определяем статус
            # Робокасса отправляет webhook только при успешной оплате
            status = "succeeded"
            
            return WebhookData(
                provider_id=self.provider.id,
                external_payment_id=external_payment_id,
                status=status,
                amount=amount,
                currency="RUB",
                metadata={
                    "robokassa_data": webhook_data
                },
                raw_data=webhook_data
            )
            
        except Exception as e:
            self.logger.error(f"Error processing Robokassa webhook: {e}")
            raise
    
    async def validate_webhook_signature(self, webhook_data: Dict[str, Any]) -> bool:
        """
        Валидация подписи webhook от Робокассы
        
        Args:
            webhook_data: Данные webhook
            
        Returns:
            bool: True если подпись валидна
        """
        try:
            # Получаем подпись из параметров
            received_signature = webhook_data.get('SignatureValue', '').lower()
            
            # Параметры для проверки подписи (без MerchantLogin для результата)
            signature_params = {
                'OutSum': webhook_data.get('OutSum'),
                'InvId': webhook_data.get('InvId')
            }
            
            # Генерируем ожидаемую подпись
            expected_signature = self._generate_signature(signature_params, self.password2)
            
            # Сравниваем подписи
            is_valid = hmac.compare_digest(received_signature, expected_signature.lower())
            
            if not is_valid:
                self.logger.warning(f"Invalid Robokassa signature for invoice {webhook_data.get('InvId')}")
            
            return is_valid
            
        except Exception as e:
            self.logger.error(f"Error validating Robokassa signature: {e}")
            return False
    
    async def test_connection(self) -> tuple[bool, str]:
        """
        Тестирование подключения к Робокассе
        
        Returns:
            tuple[bool, str]: (успешность, сообщение)
        """
        try:
            # Проверяем конфигурацию
            if not all([self.shop_id, self.password1, self.password2]):
                return False, "Неполная конфигурация Робокассы"
            
            # Пробуем создать тестовый URL
            test_params = {
                'MerchantLogin': self.shop_id,
                'OutSum': '1.00',
                'InvId': 'test_' + str(int(datetime.now().timestamp()))
            }
            
            signature = self._generate_signature(test_params, self.password1)
            
            if signature:
                return True, "Подключение к Робокассе настроено корректно"
            else:
                return False, "Ошибка генерации подписи"
                
        except Exception as e:
            return False, f"Ошибка тестирования: {str(e)}"
    
    def get_webhook_url(self) -> str:
        """Получение URL для webhook"""
        return self.provider.webhook_url or ""
    
    def get_success_url(self) -> str:
        """Получение URL для успешного платежа"""
        return self.get_config_value("success_url", "")
    
    def get_fail_url(self) -> str:
        """Получение URL для неуспешного платежа"""
        return self.get_config_value("fail_url", "")


# Регистрируем процессор в фабрике
PaymentProcessorFactory.register_processor(PaymentProviderType.robokassa, RobokassaProcessor) 