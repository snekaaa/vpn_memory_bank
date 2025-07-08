import asyncio
import json
import uuid
from decimal import Decimal
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

import aiohttp
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.payment import Payment, PaymentStatus, PaymentMethod
from models.user import User
from models.subscription import Subscription
from config.database import get_db_session


class YooKassaPaymentService:
    """
    Сервис для работы с платежами через YooKassa API
    
    Реализует создание платежей, обработку webhook'ов и проверку статусов
    """
    
    def __init__(self):
        # Тестовый ключ YooKassa
        self.api_key = "test_hJSKx6n2YdF10gLVyQMl1j0yvksIuwnCCd4pqMgFsGo"
        self.shop_id = "551050"  # Тестовый shop_id для live_ключа
        self.base_url = "https://api.yookassa.ru/v3"
        
        # Headers для API запросов
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Basic {self._encode_credentials()}",
        }
    
    def _encode_credentials(self) -> str:
        """Кодирование credentials для Basic Auth"""
        import base64
        credentials = f"{self.shop_id}:{self.api_key}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return encoded
    
    async def create_payment(
        self,
        user_id: int,
        subscription_id: int,
        amount: float,
        description: str = "VPN подписка",
        return_url: str = "https://vpn-bezlagov.ru/payment/success",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Создание платежа в YooKassa
        
        Args:
            user_id: ID пользователя
            subscription_id: ID подписки
            amount: Сумма платежа
            description: Описание платежа
            return_url: URL возврата после оплаты
            metadata: Дополнительные метаданные
            
        Returns:
            Словарь с данными созданного платежа
        """
        try:
            # Генерируем уникальный ключ идемпотентности
            idempotence_key = str(uuid.uuid4())
            
            # Подготавливаем данные платежа
            payment_data = {
                "amount": {
                    "value": f"{amount:.2f}",
                    "currency": "RUB"
                },
                "confirmation": {
                    "type": "redirect",
                    "return_url": return_url
                },
                "capture": True,
                "description": description,
                "metadata": metadata or {
                    "user_id": str(user_id),
                    "subscription_id": str(subscription_id),
                    "source": "vpn_bezlagov_bot"
                }
            }
            
            # Отправляем запрос в YooKassa
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/payments",
                    headers={
                        **self.headers,
                        "Idempotence-Key": idempotence_key
                    },
                    json=payment_data
                ) as response:
                    
                    if response.status == 200:
                        yookassa_payment = await response.json()
                        
                        # Сохраняем платеж в нашей БД
                        db_payment = await self._save_payment_to_db(
                            user_id=user_id,
                            subscription_id=subscription_id,
                            amount=amount,
                            yookassa_data=yookassa_payment,
                            description=description
                        )
                        
                        return {
                            "success": True,
                            "payment_id": db_payment.id,
                            "yookassa_id": yookassa_payment["id"],
                            "confirmation_url": yookassa_payment["confirmation"]["confirmation_url"],
                            "status": yookassa_payment["status"],
                            "amount": amount
                        }
                    else:
                        error_data = await response.json()
                        return {
                            "success": False,
                            "error": f"YooKassa API error: {error_data}",
                            "status_code": response.status
                        }
                        
        except Exception as e:
            return {
                "success": False,
                "error": f"Payment creation failed: {str(e)}"
            }
    
    async def _save_payment_to_db(
        self,
        user_id: int,
        subscription_id: int,
        amount: float,
        yookassa_data: Dict[str, Any],
        description: str
    ) -> Payment:
        """Сохранение платежа в базу данных"""
        
        async with get_db_session() as db:
            # Создаем новый платеж
            payment = Payment(
                user_id=user_id,
                subscription_id=subscription_id,
                external_id=yookassa_data["id"],
                amount=amount,
                currency="RUB",
                status=self._convert_yookassa_status(yookassa_data["status"]),
                payment_method=PaymentMethod.YOOKASSA_CARD,
                confirmation_url=yookassa_data["confirmation"]["confirmation_url"],
                external_payment_id=yookassa_data["id"],
                external_data=yookassa_data,
                description=description
            )
            
            db.add(payment)
            await db.commit()
            await db.refresh(payment)
            
            return payment
    
    def _convert_yookassa_status(self, yookassa_status: str) -> PaymentStatus:
        """Конвертация статуса YooKassa в наш enum"""
        status_mapping = {
            "pending": PaymentStatus.PENDING,
            "waiting_for_capture": PaymentStatus.PROCESSING,
            "succeeded": PaymentStatus.SUCCEEDED,
            "canceled": PaymentStatus.CANCELLED
        }
        return status_mapping.get(yookassa_status, PaymentStatus.PENDING)
    
    async def check_payment_status(self, yookassa_payment_id: str) -> Dict[str, Any]:
        """
        Проверка статуса платежа в YooKassa
        
        Args:
            yookassa_payment_id: ID платежа в YooKassa
            
        Returns:
            Словарь со статусом платежа
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/payments/{yookassa_payment_id}",
                    headers=self.headers
                ) as response:
                    
                    if response.status == 200:
                        payment_data = await response.json()
                        
                        # Обновляем статус в нашей БД
                        await self._update_payment_status(yookassa_payment_id, payment_data)
                        
                        return {
                            "success": True,
                            "status": payment_data["status"],
                            "amount": payment_data["amount"]["value"],
                            "paid": payment_data["status"] == "succeeded"
                        }
                    else:
                        return {
                            "success": False,
                            "error": f"Failed to check payment status: {response.status}"
                        }
                        
        except Exception as e:
            return {
                "success": False,
                "error": f"Status check failed: {str(e)}"
            }
    
    async def _update_payment_status(
        self,
        yookassa_payment_id: str,
        yookassa_data: Dict[str, Any]
    ) -> Optional[Payment]:
        """Обновление статуса платежа в БД"""
        
        async with get_db_session() as db:
            # Находим платеж по external_id
            stmt = select(Payment).where(Payment.external_id == yookassa_payment_id)
            result = await db.execute(stmt)
            payment = result.scalar_one_or_none()
            
            if payment:
                # Обновляем статус
                payment.status = self._convert_yookassa_status(yookassa_data["status"])
                payment.external_data = yookassa_data
                payment.updated_at = datetime.utcnow()
                
                # Если платеж успешен, отмечаем время оплаты
                if payment.status == PaymentStatus.SUCCEEDED:
                    payment.paid_at = datetime.utcnow()
                
                await db.commit()
                await db.refresh(payment)
                
                return payment
        
        return None
    
    async def process_webhook(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Обработка webhook от YooKassa
        
        Args:
            webhook_data: Данные webhook от YooKassa
            
        Returns:
            Результат обработки
        """
        try:
            event_type = webhook_data.get("event")
            payment_object = webhook_data.get("object")
            
            if not payment_object:
                return {"success": False, "error": "Missing payment object"}
            
            payment_id = payment_object.get("id")
            
            if event_type == "payment.succeeded":
                # Обновляем статус успешного платежа
                payment = await self._update_payment_status(payment_id, payment_object)
                
                if payment:
                    # Активируем подписку после успешной оплаты
                    await self._activate_subscription_after_payment(payment)
                    
                    return {
                        "success": True,
                        "message": "Payment processed successfully",
                        "payment_id": payment.id
                    }
            
            elif event_type == "payment.canceled":
                # Обновляем статус отмененного платежа
                await self._update_payment_status(payment_id, payment_object)
                
                return {
                    "success": True,
                    "message": "Payment cancellation processed"
                }
            
            return {
                "success": True,
                "message": f"Webhook {event_type} processed"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Webhook processing failed: {str(e)}"
            }
    
    async def _activate_subscription_after_payment(self, payment: Payment) -> None:
        """Активация подписки после успешного платежа"""
        
        if not payment.subscription_id:
            return
        
        async with get_db_session() as db:
            # Получаем подписку
            stmt = select(Subscription).where(Subscription.id == payment.subscription_id)
            result = await db.execute(stmt)
            subscription = result.scalar_one_or_none()
            
            if subscription:
                from models.subscription import SubscriptionStatus
                
                # Активируем подписку
                subscription.status = SubscriptionStatus.ACTIVE
                subscription.activated_at = datetime.utcnow()
                
                # Рассчитываем дату окончания на основе типа
                if subscription.type.value == "monthly":
                    subscription.expires_at = datetime.utcnow() + timedelta(days=30)
                elif subscription.type.value == "yearly":
                    subscription.expires_at = datetime.utcnow() + timedelta(days=365)
                
                await db.commit()


# Глобальный экземпляр сервиса
payment_service = YooKassaPaymentService()


async def create_payment_for_subscription(
    user_id: int,
    subscription_id: int,
    amount: float,
    description: str = "VPN подписка"
) -> Dict[str, Any]:
    """
    Упрощенная функция создания платежа для подписки
    
    Args:
        user_id: ID пользователя
        subscription_id: ID подписки
        amount: Сумма платежа
        description: Описание платежа
        
    Returns:
        Результат создания платежа
    """
    return await payment_service.create_payment(
        user_id=user_id,
        subscription_id=subscription_id,
        amount=amount,
        description=description
    )


async def check_payment_by_id(payment_id: int) -> Dict[str, Any]:
    """
    Проверка статуса платежа по ID в нашей БД
    
    Args:
        payment_id: ID платежа в нашей БД
        
    Returns:
        Статус платежа
    """
    async with get_db_session() as db:
        stmt = select(Payment).where(Payment.id == payment_id)
        result = await db.execute(stmt)
        payment = result.scalar_one_or_none()
        
        if not payment:
            return {"success": False, "error": "Payment not found"}
        
        # Проверяем статус в YooKassa если платеж еще не завершен
        if payment.status == PaymentStatus.PENDING:
            status_result = await payment_service.check_payment_status(payment.external_id)
            if status_result["success"]:
                return {
                    "success": True,
                    "payment_id": payment.id,
                    "status": status_result["status"],
                    "amount": payment.amount,
                    "paid": status_result["paid"]
                }
        
        return {
            "success": True,
            "payment_id": payment.id,
            "status": payment.status.value,
            "amount": payment.amount,
            "paid": payment.is_successful
        } 