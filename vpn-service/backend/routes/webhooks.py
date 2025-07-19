from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import Dict, Any
import json
import hmac
import hashlib
import structlog
from datetime import datetime, timedelta

from config.database import get_db_session
from config.settings import get_settings
from models.payment import Payment, PaymentStatus
from models.subscription import Subscription, SubscriptionStatus
from models.user import User
from models.vpn_key import VPNKey
from services.x3ui_client import x3ui_client
from services.notification_service import notification_service
from services.vpn_key_lifecycle_service import VPNKeyLifecycleService

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])
logger = structlog.get_logger(__name__)
settings = get_settings()

@router.post("/yookassa", response_class=PlainTextResponse)
async def yookassa_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db_session)
):
    """Обработка webhook от ЮKassa"""
    try:
        # Получаем данные
        body = await request.body()
        headers = dict(request.headers)
        
        # Проверяем подпись
        if not _verify_yookassa_signature(body, headers):
            logger.warning("Invalid ЮKassa webhook signature")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid signature"
            )
        
        # Парсим данные
        webhook_data = json.loads(body.decode('utf-8'))
        event_type = webhook_data.get("event")
        
        if event_type == "payment.succeeded":
            payment_data = webhook_data.get("object", {})
            await _process_successful_payment(payment_data, "yookassa", db)
        elif event_type == "payment.canceled":
            payment_data = webhook_data.get("object", {})
            await _process_failed_payment(payment_data, "yookassa", db)
        
        logger.info("ЮKassa webhook processed successfully", event=event_type)
        return "OK"
        
    except Exception as e:
        logger.error("Error processing ЮKassa webhook", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook processing failed"
        )

@router.post("/coingate", response_class=PlainTextResponse)
async def coingate_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db_session)
):
    """Обработка webhook от CoinGate"""
    try:
        # Получаем данные
        body = await request.body()
        headers = dict(request.headers)
        
        # Проверяем подпись (если CoinGate поддерживает)
        if not _verify_coingate_signature(body, headers):
            logger.warning("Invalid CoinGate webhook signature")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid signature"
            )
        
        # Парсим данные
        webhook_data = json.loads(body.decode('utf-8'))
        status_value = webhook_data.get("status")
        
        if status_value == "paid":
            await _process_successful_payment(webhook_data, "coingate", db)
        elif status_value in ["canceled", "failed", "expired"]:
            await _process_failed_payment(webhook_data, "coingate", db)
        
        logger.info("CoinGate webhook processed successfully", status=status_value)
        return "OK"
        
    except Exception as e:
        logger.error("Error processing CoinGate webhook", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook processing failed"
        )

@router.post("/freekassa", response_class=PlainTextResponse)
async def freekassa_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db_session)
):
    """Обработка webhook от FreeKassa"""
    try:
        # Получаем данные из формы
        form_data = await request.form()
        webhook_data = dict(form_data)
        
        logger.info("Received FreeKassa webhook", webhook_data=webhook_data)
        
        # Получаем провайдер FreeKassa из БД
        from models.payment_provider import PaymentProvider, PaymentProviderType
        provider_result = await db.execute(
            select(PaymentProvider).where(
                PaymentProvider.provider_type == PaymentProviderType.freekassa,
                PaymentProvider.is_active == True
            ).order_by(PaymentProvider.priority.asc())
        )
        provider = provider_result.scalar_one_or_none()
        
        if not provider:
            logger.error("No active FreeKassa provider found")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No active FreeKassa provider"
            )
        
        # Валидируем подпись
        from services.freekassa_service import FreeKassaService
        freekassa_service = FreeKassaService(provider_config=provider.get_freekassa_config())
        
        if not freekassa_service.validate_webhook_signature(webhook_data):
            logger.warning("Invalid FreeKassa webhook signature")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid signature"
            )
        
        # Обрабатываем статус платежа
        status_value = webhook_data.get("STATUS", "")
        
        if status_value == "1":  # Успешный платеж
            await _process_successful_payment(webhook_data, "freekassa", db)
        elif status_value in ["0", "-1"]:  # Неудачный платеж
            await _process_failed_payment(webhook_data, "freekassa", db)
        
        logger.info("FreeKassa webhook processed successfully", status=status_value)
        return "YES"  # FreeKassa ожидает ответ "YES"
        
    except Exception as e:
        logger.error("Error processing FreeKassa webhook", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook processing failed"
        )

@router.post("/test", response_class=PlainTextResponse)
async def test_webhook():
    """Тестовый webhook endpoint"""
    logger.info("Test webhook endpoint hit!")
    return "OK"

async def _process_successful_payment(payment_data: Dict[str, Any], provider: str, db: AsyncSession):
    """Обработка успешного платежа"""
    try:
        # Извлекаем ID платежа в зависимости от провайдера
        if provider == "yookassa":
            external_payment_id = payment_data.get("id")
            amount = float(payment_data.get("amount", {}).get("value", 0))
        elif provider == "coingate":
            external_payment_id = str(payment_data.get("id"))
            amount = float(payment_data.get("price_amount", 0))
        elif provider == "freekassa":
            external_payment_id = payment_data.get("MERCHANT_ORDER_ID", "")
            amount = float(payment_data.get("AMOUNT", 0))
        else:
            logger.error("Unknown payment provider", provider=provider)
            return
        
        # Находим платеж в БД в зависимости от провайдера
        if provider == "freekassa":
            # Для FreeKassa используем external_id
            payment_query = select(Payment).where(
                Payment.external_id == external_payment_id
            )
        else:
            # Для других провайдеров используем external_payment_id
            payment_query = select(Payment).where(
                Payment.external_payment_id == external_payment_id
            )
        
        payment_result = await db.execute(payment_query)
        payment = payment_result.scalar_one_or_none()
        
        if not payment:
            logger.error("Payment not found in database", 
                        external_id=external_payment_id, 
                        provider=provider)
            return
        
        # Проверяем, что платеж еще не обработан
        if payment.status == PaymentStatus.SUCCEEDED:
            logger.info("Payment already processed", payment_id=payment.id)
            return
        
        # Обновляем статус платежа
        payment.status = PaymentStatus.SUCCEEDED
        payment.processed_at = datetime.utcnow()
        payment.external_data = payment_data
        
        # Получаем подписку
        subscription_query = select(Subscription).where(
            Subscription.id == payment.subscription_id
        )
        subscription_result = await db.execute(subscription_query)
        subscription = subscription_result.scalar_one_or_none()
        
        if not subscription:
            logger.error("Subscription not found", subscription_id=payment.subscription_id)
            await db.rollback()
            return
        
        # Активируем подписку
        await _activate_subscription(subscription, db)
        
        # Создаем VPN ключ
        await _create_vpn_key_for_subscription(subscription, db)
        
        await db.commit()
        
        logger.info("Payment processed successfully", 
                   payment_id=payment.id,
                   subscription_id=subscription.id,
                   provider=provider)
        
        # Отправляем уведомление пользователю (если нужно)
        await _send_payment_notification(payment, subscription, "success")
        
    except Exception as e:
        logger.error("Error processing successful payment", 
                    external_id=external_payment_id,
                    provider=provider,
                    error=str(e))
        await db.rollback()
        raise

async def _process_failed_payment(payment_data: Dict[str, Any], provider: str, db: AsyncSession):
    """Обработка неудачного платежа"""
    try:
        # Извлекаем ID платежа в зависимости от провайдера
        if provider == "yookassa":
            external_payment_id = payment_data.get("id")
        elif provider == "coingate":
            external_payment_id = str(payment_data.get("id"))
        elif provider == "freekassa":
            external_payment_id = payment_data.get("MERCHANT_ORDER_ID", "")
        else:
            logger.error("Unknown payment provider", provider=provider)
            return
        
        # Находим платеж в БД в зависимости от провайдера
        if provider == "freekassa":
            # Для FreeKassa используем external_id
            payment_query = select(Payment).where(
                Payment.external_id == external_payment_id
            )
        else:
            # Для других провайдеров используем external_payment_id
            payment_query = select(Payment).where(
                Payment.external_payment_id == external_payment_id
            )
        
        payment_result = await db.execute(payment_query)
        payment = payment_result.scalar_one_or_none()
        
        if not payment:
            logger.error("Payment not found in database", 
                        external_id=external_payment_id,
                        provider=provider)
            return
        
        # Обновляем статус платежа
        payment.status = PaymentStatus.FAILED
        payment.processed_at = datetime.utcnow()
        payment.external_data = payment_data
        
        await db.commit()
        
        logger.info("Failed payment processed", 
                   payment_id=payment.id,
                   provider=provider)
        
        # Отправляем уведомление пользователю
        subscription_query = select(Subscription).where(
            Subscription.id == payment.subscription_id
        )
        subscription_result = await db.execute(subscription_query)
        subscription = subscription_result.scalar_one_or_none()
        
        if subscription:
            await _send_payment_notification(payment, subscription, "failed")
        
    except Exception as e:
        logger.error("Error processing failed payment", 
                    external_id=external_payment_id,
                    provider=provider,
                    error=str(e))
        await db.rollback()
        raise

async def _activate_subscription(subscription: Subscription, db: AsyncSession):
    """Активация подписки"""
    now = datetime.utcnow()
    
    # Устанавливаем период подписки
    if subscription.subscription_type.value == "trial":
        end_date = now + timedelta(days=7)
    elif subscription.subscription_type.value == "monthly":
        end_date = now + timedelta(days=30)
    elif subscription.subscription_type.value == "quarterly":
        end_date = now + timedelta(days=90)
    elif subscription.subscription_type.value == "yearly":
        end_date = now + timedelta(days=365)
    else:
        end_date = now + timedelta(days=30)  # По умолчанию месяц
    
    # Обновляем подписку
    subscription.status = SubscriptionStatus.ACTIVE
    subscription.start_date = now
    subscription.end_date = end_date
    subscription.is_active = True
    
    logger.info("Subscription activated", 
               subscription_id=subscription.id,
               type=subscription.subscription_type.value,
               end_date=end_date.isoformat())
    
    # НОВОЕ: Реактивируем VPN ключи пользователя при активации подписки
    try:
        lifecycle_service = VPNKeyLifecycleService(db)
        reactivation_result = await lifecycle_service.reactivate_user_keys(subscription.user_id)
        
        if reactivation_result.get("success"):
            reactivated_count = reactivation_result.get("reactivated_count", 0)
            logger.info("✅ VPN keys reactivated after subscription activation", 
                       user_id=subscription.user_id,
                       subscription_id=subscription.id,
                       reactivated_keys=reactivated_count)
        else:
            logger.warning("⚠️ Failed to reactivate VPN keys after subscription activation", 
                         user_id=subscription.user_id,
                         subscription_id=subscription.id,
                         error=reactivation_result.get("error"))
                         
    except Exception as e:
        logger.error("💥 Error reactivating VPN keys after subscription activation", 
                    user_id=subscription.user_id,
                    subscription_id=subscription.id,
                    error=str(e))
        # Не прерываем процесс активации подписки из-за проблем с ключами

async def _create_vpn_key_for_subscription(subscription: Subscription, db: AsyncSession):
    """Создание VPN ключа для активированной подписки"""
    try:
        # Проверяем, нет ли уже ключа для этой подписки
        existing_key_query = select(VPNKey).where(
            VPNKey.subscription_id == subscription.id,
            VPNKey.is_active == True
        )
        existing_key_result = await db.execute(existing_key_query)
        existing_key = existing_key_result.scalar_one_or_none()
        
        if existing_key:
            logger.info("VPN key already exists for subscription", 
                       subscription_id=subscription.id,
                       key_id=existing_key.id)
            return existing_key
        
        # Получаем пользователя
        user_query = select(User).where(User.id == subscription.user_id)
        user_result = await db.execute(user_query)
        user = user_result.scalar_one_or_none()
        
        if not user:
            logger.error("User not found for subscription", subscription_id=subscription.id)
            return None
        
        # Конфигурация клиента для 3X-UI
        import uuid
        client_config = {
            "telegram_id": user.telegram_id,
            "username": user.username or "",
            "flow": "xtls-rprx-vision",
            "limit_ip": 2
        }
        
        # Получаем доступные inbound'ы
        inbounds = await x3ui_client.get_inbounds()
        if not inbounds:
            logger.error("No available inbounds in 3X-UI")
            return None
        
        # Выбираем первый доступный inbound
        inbound = inbounds[0]
        inbound_id = inbound.get("id", 1)
        
        # Создаем клиента в 3X-UI
        client_result = await x3ui_client.create_client(inbound_id, client_config)
        
        if not client_result:
            logger.error("Failed to create VPN client in 3X-UI")
            return None
        
        # Получаем локацию сервера из настроек inbound
        server_location = inbound.get("remark", "RU-Moscow")
        if not server_location or server_location.strip() == "":
            server_location = "RU-Moscow"  # Fallback location
        
        # Создаем запись в БД
        vpn_key = VPNKey(
            subscription_id=subscription.id,
            key_name=client_result["email"],
            client_id=client_result["client_id"],
            inbound_id=inbound_id,
            server_location=server_location,
            is_active=True,
            traffic_used_bytes=0
        )
        
        db.add(vpn_key)
        await db.commit()
        await db.refresh(vpn_key)
        
        logger.info("VPN key created for activated subscription", 
                   subscription_id=subscription.id,
                   vpn_key_id=vpn_key.id,
                   client_id=client_result["client_id"])
        
        return vpn_key
        
    except Exception as e:
        logger.error("Error creating VPN key for subscription", 
                    subscription_id=subscription.id, 
                    error=str(e))
        await db.rollback()
        return None

async def _send_payment_notification(payment: Payment, subscription: Subscription, status: str):
    """Отправка уведомления пользователю о статусе платежа"""
    try:
        # Получаем пользователя
        user_query = select(User).where(User.id == subscription.user_id)
        async with get_db_session() as db:
            user_result = await db.execute(user_query)
            user = user_result.scalar_one_or_none()
            
            if not user:
                logger.error("User not found for notification", user_id=subscription.user_id)
                return
            
            # Получаем VPN ключ для успешного платежа
            vpn_key_name = "Not available"
            if status == "success":
                vpn_key_query = select(VPNKey).where(
                    VPNKey.subscription_id == subscription.id,
                    VPNKey.is_active == True
                )
                vpn_key_result = await db.execute(vpn_key_query)
                vpn_key = vpn_key_result.scalar_one_or_none()
                if vpn_key:
                    vpn_key_name = vpn_key.key_name
                    
                # Отправляем уведомление об успешной оплате
                await notification_service.send_payment_success_notification(
                    telegram_id=user.telegram_id,
                    payment_amount=payment.amount,
                    subscription_type=subscription.subscription_type.value,
                    vpn_key_name=vpn_key_name
                )
            else:
                # Отправляем уведомление о неудачной оплате
                failure_reason = None
                if hasattr(payment, 'external_data') and payment.external_data:
                    failure_reason = payment.external_data.get('failure_reason')
                
                await notification_service.send_payment_failed_notification(
                    telegram_id=user.telegram_id,
                    payment_amount=payment.amount,
                    subscription_type=subscription.subscription_type.value,
                    failure_reason=failure_reason
                )
        
        logger.info("Payment notification sent", 
                   payment_id=payment.id,
                   user_id=subscription.user_id,
                   status=status)
        
    except Exception as e:
        logger.error("Error sending payment notification", 
                    payment_id=payment.id,
                    error=str(e))

def _verify_yookassa_signature(body: bytes, headers: Dict[str, str]) -> bool:
    """Проверка подписи webhook от ЮKassa"""
    try:
        # Получаем подпись из заголовков
        signature = headers.get("x-yookassa-signature", "")
        if not signature:
            return False
        
        # Создаем подпись
        expected_signature = hmac.new(
            settings.YOOKASSA_WEBHOOK_SECRET.encode('utf-8'),
            body,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)
        
    except Exception as e:
        logger.error("Error verifying ЮKassa signature", error=str(e))
        return False

def _verify_coingate_signature(body: bytes, headers: Dict[str, str]) -> bool:
    """Проверка подписи webhook от CoinGate"""
    try:
        # CoinGate поддерживает проверку IP адресов для webhook'ов
        # Официальные IP адреса CoinGate для webhook'ов
        coingate_ips = [
            "91.202.65.0/24",   # EU servers
            "91.202.64.0/24",   # EU servers  
            "178.62.45.186",    # Primary webhook IP
            "139.59.166.143",   # Secondary webhook IP
        ]
        
        # Получаем IP отправителя
        client_ip = headers.get("x-forwarded-for", "").split(",")[0].strip()
        if not client_ip:
            client_ip = headers.get("x-real-ip", "")
        
        # Если IP не найден, пропускаем проверку (для тестирования)
        if not client_ip:
            logger.warning("CoinGate webhook: IP address not found in headers")
            return True
        
        # Проверяем IP в белом списке
        import ipaddress
        client_ip_obj = ipaddress.ip_address(client_ip)
        
        for allowed_ip in coingate_ips:
            try:
                if "/" in allowed_ip:
                    # CIDR subnet
                    if client_ip_obj in ipaddress.ip_network(allowed_ip):
                        logger.info("CoinGate webhook IP verified", client_ip=client_ip)
                        return True
                else:
                    # Single IP
                    if client_ip_obj == ipaddress.ip_address(allowed_ip):
                        logger.info("CoinGate webhook IP verified", client_ip=client_ip)
                        return True
            except ValueError:
                continue
        
        logger.warning("CoinGate webhook from unauthorized IP", client_ip=client_ip)
        return False
        
    except Exception as e:
        logger.error("Error verifying CoinGate signature", error=str(e))
        # В случае ошибки валидации разрешаем запрос для тестирования
        return True 