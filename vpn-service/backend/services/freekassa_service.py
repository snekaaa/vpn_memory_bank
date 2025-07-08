"""
FreeKassa Payment Service Implementation using API
Реализация платежного сервиса FreeKassa с использованием API
"""
import hashlib
import hmac
import time
import aiohttp
import urllib.parse
from typing import Optional, Dict, Any
import structlog
import json

logger = structlog.get_logger(__name__)

class FreeKassaService:
    """
    Сервис для работы с FreeKassa платежной системой через API
    """
    
    def __init__(self, merchant_id: str, api_key: str, secret_word_1: str, secret_word_2: str):
        """
        Инициализация сервиса FreeKassa
        
        Args:
            merchant_id: ID магазина (shopId)
            api_key: API ключ
            secret_word_1: Секретное слово для формы оплаты
            secret_word_2: Секретное слово для webhook
        """
        self.merchant_id = merchant_id
        self.api_key = api_key
        self.secret_word_1 = secret_word_1
        self.secret_word_2 = secret_word_2
        self.api_base_url = "https://api.fk.life/v1"
        
        logger.info("FreeKassa service initialized", merchant_id=merchant_id)
        
    def _generate_api_signature(self, data: Dict[str, Any]) -> str:
        """
        Генерация подписи для API запросов
        Согласно документации: сортируем параметры по ключам, объединяем значения с разделителем |
        """
        # Исключаем signature из данных если он есть
        filtered_data = {k: v for k, v in data.items() if k != 'signature'}
        
        # Сортируем по ключам
        sorted_keys = sorted(filtered_data.keys())
        
        # Объединяем значения разделителем |
        values = [str(filtered_data[key]) for key in sorted_keys]
        signature_string = '|'.join(values)
        
        logger.info(f"FreeKassa signature string: {signature_string}")
        
        # Создаем HMAC SHA256 подпись
        signature = hmac.new(
            self.api_key.encode('utf-8'),
            signature_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    async def create_payment_url(self, amount: float, order_id: str, 
                                currency: str = "RUB", email: Optional[str] = None, 
                                user_ip: str = "127.0.0.1", payment_system_id: int = 4) -> str:
        """
        Создание платежа через FreeKassa API
        
        Args:
            amount: Сумма платежа
            order_id: ID заказа в нашей системе
            currency: Валюта (по умолчанию RUB)
            email: Email плательщика
            user_ip: IP адрес плательщика
            payment_system_id: ID платежной системы (4 = VISA/MasterCard)
        
        Returns:
            URL для перенаправления на оплату
        """
        try:
            # Генерируем nonce (уникальный ID запроса)
            nonce = int(time.time())
            
            # Подготавливаем данные для запроса
            data = {
                'shopId': int(self.merchant_id),
                'nonce': nonce,
                'paymentId': str(order_id),
                'i': payment_system_id,
                'email': email or 'noreply@system.local',
                'ip': user_ip,
                'amount': float(amount),
                'currency': currency
            }
            
            # Генерируем подпись
            signature = self._generate_api_signature(data)
            data['signature'] = signature
            
            logger.info(f"FreeKassa API request data: {data}")
            
            # Делаем запрос к API
            url = f"{self.api_base_url}/orders/create"
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data) as response:
                    response_text = await response.text()
                    logger.info(f"FreeKassa API response status: {response.status}")
                    logger.info(f"FreeKassa API response: {response_text}")
                    
                    if response.status == 200:
                        result = await response.json()
                        
                        if result.get('type') == 'success':
                            payment_url = result.get('location')
                            if payment_url:
                                logger.info(f"FreeKassa payment URL created: {payment_url}")
                                return payment_url
                            else:
                                logger.error(f"No location in FreeKassa response: {result}")
                                raise Exception("Получен ответ без ссылки на оплату")
                        else:
                            logger.error(f"FreeKassa API error: {result}")
                            raise Exception(f"Ошибка API FreeKassa: {result}")
                    else:
                        logger.error(f"FreeKassa API HTTP error {response.status}: {response_text}")
                        raise Exception(f"Ошибка HTTP {response.status} от FreeKassa")
        
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error creating FreeKassa payment: {e}")
            
            # Проверяем специфичные ошибки FreeKassa для более понятных сообщений
            if "Merchant not activated" in error_msg or "401" in error_msg:
                raise Exception("🚫 Платежная система FreeKassa временно недоступна. Свяжитесь с поддержкой для активации альтернативных способов оплаты.")
            elif "HTTP 400" in error_msg:
                raise Exception("🔧 Неверные параметры платежа. Обратитесь в техническую поддержку.")
            elif "HTTP 403" in error_msg:
                raise Exception("🔐 Доступ к платежной системе ограничен. Обратитесь в поддержку.")
            elif "HTTP 500" in error_msg:
                raise Exception("⚙️ Внутренняя ошибка платежной системы. Попробуйте позже или обратитесь в поддержку.")
            else:
                raise Exception(f"💳 Ошибка создания платежа: {error_msg}")
    
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
            
            # Формирование строки для проверки подписи согласно документации
            signature_string = (
                f"{webhook_data.get('MERCHANT_ORDER_ID', '')}:"
                f"{webhook_data.get('AMOUNT', '')}:"
                f"{self.secret_word_2}"
            )
            
            expected_sign = hashlib.md5(signature_string.encode('utf-8')).hexdigest()
            
            return hmac.compare_digest(received_sign.lower(), expected_sign.lower())
            
        except Exception as e:
            logger.error(f"Error validating FreeKassa webhook signature: {e}")
            return False
    
    async def process_webhook(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Обработка webhook уведомления от FreeKassa
        
        Args:
            webhook_data: Данные webhook
        
        Returns:
            Обработанные данные платежа
        """
        try:
            # Проверяем подпись
            if not self._validate_webhook_signature(webhook_data):
                raise Exception("Неверная подпись webhook")
            
            # Извлекаем данные платежа
            payment_data = {
                'external_payment_id': webhook_data.get('intid'),  # ID платежа в FreeKassa
                'order_id': webhook_data.get('MERCHANT_ORDER_ID'),  # Наш ID заказа
                'amount': float(webhook_data.get('AMOUNT', 0)),
                'currency': webhook_data.get('CURRENCY', 'RUB'),
                'status': 'completed',  # FreeKassa присылает webhook только при успешной оплате
                'payer_details': {
                    'email': webhook_data.get('MERCHANT_ORDER_ID')  # В FreeKassa нет отдельного поля email в webhook
                }
            }
            
            logger.info(f"FreeKassa webhook processed: {payment_data}")
            return payment_data
            
        except Exception as e:
            logger.error(f"Error processing FreeKassa webhook: {e}")
            raise
    
    async def check_payment_status(self, payment_id: str) -> Dict[str, Any]:
        """
        Проверка статуса платежа через API
        
        Args:
            payment_id: ID платежа для проверки
        
        Returns:
            Статус платежа
        """
        try:
            # Генерируем nonce
            nonce = int(time.time())
            
            # Подготавливаем данные для запроса
            data = {
                'shopId': int(self.merchant_id),
                'nonce': nonce,
                'paymentId': str(payment_id)
            }
            
            # Генерируем подпись
            signature = self._generate_api_signature(data)
            data['signature'] = signature
            
            # Делаем запрос к API
            url = f"{self.api_base_url}/orders"
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data) as response:
                    if response.status == 200:
                        result = await response.json()
                        
                        if result.get('type') == 'success':
                            orders = result.get('orders', [])
                            if orders:
                                order = orders[0]  # Первый заказ в списке
                                status_map = {
                                    0: 'pending',    # Новый
                                    1: 'completed',  # Оплачен
                                    6: 'refunded',   # Возврат
                                    8: 'failed',     # Ошибка
                                    9: 'cancelled'   # Отмена
                                }
                                
                                return {
                                    'status': status_map.get(order.get('status'), 'unknown'),
                                    'amount': order.get('amount'),
                                    'currency': order.get('currency'),
                                    'external_id': order.get('fk_order_id')
                                }
                        
                        return {'status': 'not_found'}
                    else:
                        raise Exception(f"HTTP {response.status}")
                        
        except Exception as e:
            logger.error(f"Error checking FreeKassa payment status: {e}")
            return {'status': 'error', 'error': str(e)} 