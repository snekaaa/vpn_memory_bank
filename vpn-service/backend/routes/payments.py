"""
Payment Routes - API endpoints для работы с платежами
Реализует создание платежей, webhook обработчики и проверку статуса
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, Request, BackgroundTasks
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, desc
from pydantic import BaseModel, Field

from config.database import get_db
from models.user import User
from models.payment import Payment, PaymentStatus, PaymentMethod
from models.payment_provider import PaymentProvider, PaymentProviderType, PaymentProviderStatus
from models.subscription import Subscription, SubscriptionStatus, SubscriptionType
# from services.payment_service import PaymentProcessorManager
from services.subscription_service import SubscriptionService
from services.service_plans_manager import ServicePlansManager
from services.robokassa_service import RobokassaService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payments", tags=["payments"])

# Pydantic модели для API
class CreatePaymentRequest(BaseModel):
    """Запрос на создание платежа"""
    user_id: int = Field(..., description="ID пользователя")
    subscription_type: str = Field(..., description="Тип подписки (monthly, quarterly, etc.)")
    service_name: Optional[str] = Field(None, description="Название услуги")
    user_email: Optional[str] = Field(None, description="Email пользователя")
    success_url: Optional[str] = Field(None, description="URL успешной оплаты")
    fail_url: Optional[str] = Field(None, description="URL неуспешной оплаты")
    provider_type: Optional[str] = Field(None, description="Тип платежного провайдера")

class CreatePaymentResponse(BaseModel):
    """Ответ на создание платежа"""
    status: str = Field(..., description="Статус операции")
    payment_id: int = Field(..., description="ID платежа")
    payment_url: str = Field(..., description="URL для оплаты")
    amount: float = Field(..., description="Сумма платежа")
    currency: str = Field(..., description="Валюта")

class PaymentStatusResponse(BaseModel):
    """Ответ с статусом платежа"""
    status: str = Field(..., description="Статус операции")
    payment_id: int = Field(..., description="ID платежа")
    payment_status: str = Field(..., description="Статус платежа")
    amount: float = Field(..., description="Сумма платежа")
    created_at: datetime = Field(..., description="Дата создания")
    paid_at: Optional[datetime] = Field(None, description="Дата оплаты")

@router.get("/plans")
async def get_subscription_plans():
    """
    Получение доступных планов подписки
    
    Returns:
        Список планов подписки
    """
    try:
        service_plans_manager = ServicePlansManager()
        plans = service_plans_manager.get_plans_for_robokassa()
        
        return {"status": "success", "plans": plans}
    except Exception as e:
        logger.error(f"Error getting subscription plans: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения планов подписки")

@router.get("/plans/bot")
async def get_subscription_plans_for_bot():
    """
    Получение планов подписки для бота
    
    Returns:
        Список планов подписки для бота
    """
    try:
        service_plans_manager = ServicePlansManager()
        plans = service_plans_manager.get_plans_for_robokassa()
        
        return {"status": "success", "plans": plans}
    except Exception as e:
        logger.error(f"Error getting bot subscription plans: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения планов подписки")

@router.post("/create", response_model=CreatePaymentResponse)
async def create_payment(
    request: CreatePaymentRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Создание платежа
    
    Args:
        request: Запрос на создание платежа
        db: Сессия базы данных
        
    Returns:
        Информация о созданном платеже
    """
    logger.info(f"Received create_payment request: {request.dict()}")
    try:
        # Проверяем существование пользователя
        result = await db.execute(
            select(User).where(User.id == request.user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        # Получаем активный провайдер выбранного типа
        provider = await get_active_provider_by_type(db, request.provider_type)
        
        if not provider:
            # Fallback к старой системе если провайдер не найден
            logger.info(f"No active {request.provider_type} provider found, using legacy system")
            robokassa_service = await get_robokassa_service(db)
            plans = robokassa_service.get_subscription_plans()
            plan = plans.get(request.subscription_type)
            
            if not plan:
                raise HTTPException(status_code=400, detail="Неверный тип подписки")
            
            # Создаем запись платежа
            payment = Payment(
                user_id=request.user_id,
                amount=plan['price'],
                currency=plan['currency'],
                status=PaymentStatus.PENDING,
                payment_method=PaymentMethod.robokassa,
                description=request.service_name or plan['description'],
                payment_metadata={
                    'subscription_type': request.subscription_type,
                    'service_name': request.service_name,
                    'duration_days': plan['duration_days']
                }
            )
            
            db.add(payment)
            await db.commit()
            await db.refresh(payment)
            
            # Создаем URL для оплаты
            payment_result = robokassa_service.create_payment_url(
                order_id=str(payment.id),
                amount=payment.amount,
                description=payment.description,
                email=request.user_email,
                success_url=request.success_url,
                failure_url=request.fail_url
            )
            payment_url = payment_result['url']
            
            # Обновляем запись с внешним ID
            payment.external_id = str(payment.id)
            payment.robokassa_invoice_id = str(payment.id)
            payment.confirmation_url = payment_url
            
            await db.commit()
            
            logger.info(f"Created payment {payment.id} for user {request.user_id} using legacy Robokassa")
            
            return CreatePaymentResponse(
                status="success",
                payment_id=payment.id,
                payment_url=payment_url,
                amount=payment.amount,
                currency=payment.currency
            )
        
        # Используем новую систему провайдеров
        logger.info(f"Found active {provider.provider_type.value} provider: {provider.name} (ID: {provider.id})")
        service_plans_manager = ServicePlansManager()
        
        # Получаем планы в зависимости от типа провайдера
        if provider.provider_type == PaymentProviderType.robokassa:
            plans = service_plans_manager.get_plans_for_robokassa()
            payment_method = PaymentMethod.robokassa
        elif provider.provider_type == PaymentProviderType.freekassa:
            plans = service_plans_manager.get_plans_for_robokassa()  # Используем те же планы
            payment_method = PaymentMethod.freekassa
        else:
            plans = service_plans_manager.get_plans_for_robokassa()  # Fallback
            payment_method = PaymentMethod.robokassa
        
        plan = plans.get(request.subscription_type)
        
        if not plan:
            raise HTTPException(status_code=400, detail="Неверный тип подписки")
        
        # Создаем запись платежа
        payment = Payment(
            user_id=request.user_id,
            amount=plan['price'],
            currency=plan['currency'],
            status=PaymentStatus.PENDING,
            payment_method=payment_method,
            description=request.service_name or plan['description'],
            provider_id=provider.id,
            payment_metadata={
                'subscription_type': request.subscription_type,
                'service_name': request.service_name,
                'duration_days': plan['duration_days']
            }
        )
        
        db.add(payment)
        await db.commit()
        await db.refresh(payment)
        
        # Используем соответствующий сервис в зависимости от типа провайдера
        logger.info(f"Found provider {provider.name}, using provider config")
        
        if provider.provider_type == PaymentProviderType.robokassa:
            # Robokassa сервис
            provider_config = provider.get_robokassa_config()
            
            # Маскируем пароли для безопасного логирования
            masked_config = provider_config.copy()
            if 'password1' in masked_config and masked_config['password1']:
                masked_config['password1'] = '********'
            if 'password2' in masked_config and masked_config['password2']:
                masked_config['password2'] = '********'
            logger.info(f"Robokassa provider config being used: {masked_config}")

            robokassa_service = RobokassaService(provider_config=provider_config)
            payment_result = robokassa_service.create_payment_url(
                order_id=str(payment.id),
                amount=payment.amount,
                description=payment.description,
                email=request.user_email,
                success_url=request.success_url,
                failure_url=request.fail_url
            )
            payment_url = payment_result['url']
            
            payment.external_id = str(payment.id)
            payment.robokassa_invoice_id = str(payment.id)
            
        elif provider.provider_type == PaymentProviderType.freekassa:
            # FreeKassa сервис - используем новый API
            from services.freekassa_service import FreeKassaService
            
            provider_config = provider.get_freekassa_config()
            
            # Маскируем ключи для безопасного логирования
            masked_config = provider_config.copy()
            if 'api_key' in masked_config and masked_config['api_key']:
                masked_config['api_key'] = '********'
            if 'secret1' in masked_config and masked_config['secret1']:
                masked_config['secret1'] = '********'
            if 'secret2' in masked_config and masked_config['secret2']:
                masked_config['secret2'] = '********'
            logger.info(f"FreeKassa provider config being used: {masked_config}")

            # Создаем новый сервис с правильными параметрами
            freekassa_service = FreeKassaService(
                merchant_id=provider_config['merchant_id'],
                api_key=provider_config['api_key'],
                secret_word_1=provider_config['secret1'],
                secret_word_2=provider_config['secret2']
            )
            
            # Используем новый API-метод
            payment_url = await freekassa_service.create_payment_url(
                amount=payment.amount,
                order_id=str(payment.id),
                currency=payment.currency,
                email=request.user_email or f"user_{request.user_id}@telegram.local",
                user_ip="127.0.0.1",  # Можно извлечь из запроса если нужно
                payment_system_id=4  # VISA/MasterCard по умолчанию
            )
            
            payment.external_id = str(payment.id)
            
        else:
            raise HTTPException(status_code=400, detail=f"Провайдер типа {provider.provider_type.value} не поддерживается")
        
        payment.confirmation_url = payment_url
        payment.provider_id = provider.id  # Связываем с провайдером
        
        await db.commit()
        
        logger.info(f"Created payment {payment.id} for user {request.user_id} using provider {provider.name}")
        
        return CreatePaymentResponse(
            status="success",
            payment_id=payment.id,
            payment_url=payment_url,
            amount=payment.amount,
            currency=payment.currency
        )
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error creating payment: {e}", exc_info=True)
        
        # Проверяем специфичные ошибки для более понятных сообщений
        error_msg = str(e)
        if "временно недоступна" in error_msg or "not activated" in error_msg:
            # Если основной провайдер недоступен, показываем сообщение с рекомендацией
            detail = f"{error_msg} Попробуйте позже или воспользуйтесь другим способом оплаты."
        elif "Неверные параметры" in error_msg:
            detail = f"{error_msg} Проверьте корректность данных или обратитесь в поддержку."
        else:
            detail = f"Ошибка создания платежа: {error_msg}"
        
        raise HTTPException(status_code=500, detail=detail)

@router.get("/{payment_id}", response_model=PaymentStatusResponse)
async def get_payment_status(
    payment_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Получение статуса платежа
    
    Args:
        payment_id: ID платежа
        db: Сессия базы данных
        
    Returns:
        Информация о статусе платежа
    """
    try:
        # Получаем платеж
        result = await db.execute(
            select(Payment).where(Payment.id == payment_id)
        )
        payment = result.scalar_one_or_none()
        
        if not payment:
            raise HTTPException(status_code=404, detail="Платеж не найден")
        
        # Если платеж еще не завершен, проверяем статус
        if payment.status == PaymentStatus.PENDING:
            if payment.provider_id:
                # Используем новую систему провайдеров
                provider_result = await db.execute(
                    select(PaymentProvider).where(PaymentProvider.id == payment.provider_id)
                )
                provider = provider_result.scalar_one_or_none()
                
                if provider:
                    # Используем конфигурацию провайдера для проверки статуса
                    logger.info(f"Found provider {provider.name}, using provider config for status check")
                    
                    if provider.provider_type == PaymentProviderType.robokassa and payment.robokassa_invoice_id:
                        robokassa_service = RobokassaService(provider_config=provider.get_robokassa_config())
                        robokassa_status = await robokassa_service.check_payment_status(
                            payment.robokassa_invoice_id
                        )
                        
                        if robokassa_status.get('status') == 'paid':
                            payment.status = PaymentStatus.SUCCEEDED
                            payment.paid_at = datetime.now(timezone.utc)
                            await db.commit()
                            
                            # Активируем подписку
                            subscription_service = SubscriptionService(db)
                            metadata = payment.payment_metadata or {}
                            subscription_type = metadata.get('subscription_type')
                            
                            if subscription_type:
                                await subscription_service.activate_subscription(
                                    user_id=payment.user_id,
                                    subscription_type=subscription_type,
                                    payment_id=payment.id
                                )
                    
                    elif provider.provider_type == PaymentProviderType.freekassa and payment.external_id:
                        from services.freekassa_service import FreeKassaService
                        
                        freekassa_service = FreeKassaService(provider_config=provider.get_freekassa_config())
                        freekassa_status = await freekassa_service.check_payment_status(
                            payment.external_id
                        )
                        
                        if freekassa_status.get('status') == 'succeeded':
                            payment.status = PaymentStatus.SUCCEEDED
                            payment.paid_at = datetime.now(timezone.utc)
                            await db.commit()
                            
                            # Активируем подписку
                            subscription_service = SubscriptionService(db)
                            metadata = payment.payment_metadata or {}
                            subscription_type = metadata.get('subscription_type')
                            
                            if subscription_type:
                                await subscription_service.activate_subscription(
                                    user_id=payment.user_id,
                                    subscription_type=subscription_type,
                                    payment_id=payment.id
                                )
            elif payment.robokassa_invoice_id:
                # Используем старую систему
                robokassa_service = await get_robokassa_service(db)
                robokassa_status = await robokassa_service.check_payment_status(
                    payment.robokassa_invoice_id
                )
                
                if robokassa_status.get('status') == 'paid':
                    payment.status = PaymentStatus.SUCCEEDED
                    payment.paid_at = datetime.now(timezone.utc)
                    await db.commit()
                    
                    # Активируем подписку
                    subscription_service = SubscriptionService(db)
                    metadata = payment.payment_metadata or {}
                    subscription_type = metadata.get('subscription_type')
                    
                    if subscription_type:
                        await subscription_service.activate_subscription(
                            user_id=payment.user_id,
                            subscription_type=subscription_type,
                            payment_id=payment.id
                        )
        
        return PaymentStatusResponse(
            status="success",
            payment_id=payment.id,
            payment_status=payment.status.value,
            amount=payment.amount,
            created_at=payment.created_at,
            paid_at=payment.paid_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting payment status: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения статуса платежа")

@router.get("/robokassa/result")
@router.post("/robokassa/result")
async def robokassa_result_handler(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Обработчик ResultURL от Робокассы (поддерживает GET и POST)
    
    Args:
        request: HTTP запрос
        background_tasks: Фоновые задачи
        db: Сессия базы данных
        
    Returns:
        Ответ для Робокассы
    """
    try:
        # Получаем параметры от Робокассы
        if request.method == "POST":
            form_data = await request.form()
            params = dict(form_data)
        else:
            params = dict(request.query_params)
        
        logger.info(f"Received Robokassa result: {params}")
        
        # Используем новую систему провайдеров если доступна
        invoice_id = params.get('InvId')
        if invoice_id:
            payment_result = await db.execute(
                select(Payment).where(Payment.external_id == invoice_id)
            )
            payment = payment_result.scalar_one_or_none()
            
            if payment and payment.provider_id:
                # Используем новую систему провайдеров
                provider_result = await db.execute(
                    select(PaymentProvider).where(PaymentProvider.id == payment.provider_id)
                )
                provider = provider_result.scalar_one_or_none()
                
                if provider:
                    # Используем конфигурацию провайдера для webhook
                    logger.info(f"Found provider {provider.name}, using provider config for webhook")
                    robokassa_service = RobokassaService(provider_config=provider.get_robokassa_config())
                    
                    # Валидируем подпись с использованием провайдера
                    if robokassa_service.validate_result_signature(params):
                        logger.info(f"Valid webhook signature for invoice {invoice_id} using provider {provider.name}")
                        
                        # Обрабатываем платеж в фоновом режиме
                        background_tasks.add_task(
                            process_robokassa_payment,
                            params,
                            db
                        )
                        
                        return PlainTextResponse(f"OK{invoice_id}")
                    else:
                        logger.warning(f"Invalid webhook signature for invoice {invoice_id} using provider {provider.name}")
                        return PlainTextResponse("Invalid signature", status_code=400)
        
        # Fallback к старой системе валидации
        robokassa_service = await get_robokassa_service(db)
        if not robokassa_service.validate_result_signature(params):
            logger.warning("Invalid signature from Robokassa")
            return PlainTextResponse("Invalid signature", status_code=400)
        
        # Обрабатываем платеж в фоновом режиме
        background_tasks.add_task(
            process_robokassa_payment,
            params,
            db
        )
        
        # Возвращаем подтверждение для Робокассы
        return PlainTextResponse(f"OK{params.get('InvId', '')}")
        
    except Exception as e:
        logger.error(f"Error processing Robokassa result: {e}")
        return PlainTextResponse("Error", status_code=500)

@router.get("/robokassa/success")
@router.post("/robokassa/success")
async def robokassa_success_handler(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Обработчик SuccessURL от Робокассы (поддерживает GET и POST)
    
    Args:
        request: HTTP запрос
        db: Сессия базы данных
        
    Returns:
        Ответ для пользователя
    """
    try:
        # Получаем параметры
        if request.method == "POST":
            form_data = await request.form()
            params = dict(form_data)
        else:
            params = dict(request.query_params)
        
        logger.info(f"Received Robokassa success: {params}")
        
        # Получаем провайдера для диагностики
        robokassa_service = await get_robokassa_service(db)
        
        # Логируем конфигурацию для диагностики
        logger.info(f"🔍 ROBOKASSA DEBUG:")
        logger.info(f"  - Shop ID: {robokassa_service.shop_id}")
        logger.info(f"  - Password1 length: {len(robokassa_service.password1) if robokassa_service.password1 else 0}")
        logger.info(f"  - Password2 length: {len(robokassa_service.password2) if robokassa_service.password2 else 0}")
        logger.info(f"  - Test mode: {robokassa_service.test_mode}")
        
        # Валидируем подпись
        if not robokassa_service.validate_success_signature(params):
            logger.error("❌ Invalid success signature from Robokassa")
            return JSONResponse(
                content={"status": "error", "message": "Invalid signature"},
                status_code=400
            )
        
        logger.info("✅ Valid Robokassa success signature")
        
        # Получаем информацию о платеже
        invoice_id = params.get('InvId')
        amount = float(params.get('OutSum', 0))
        
        return JSONResponse(content={
            "status": "success",
            "message": "Платеж успешно завершен",
            "invoice_id": invoice_id,
            "amount": amount
        })
        
    except Exception as e:
        logger.error(f"Error processing Robokassa success: {e}")
        return JSONResponse(
            content={"status": "error", "message": "Ошибка обработки"},
            status_code=500
        )

@router.get("/robokassa/fail")
@router.post("/robokassa/fail")
async def robokassa_fail_handler(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Обработчик FailURL от Робокассы (поддерживает GET и POST)
    
    Args:
        request: HTTP запрос
        db: Сессия базы данных
        
    Returns:
        Ответ для пользователя
    """
    try:
        # Получаем параметры
        if request.method == "POST":
            form_data = await request.form()
            params = dict(form_data)
        else:
            params = dict(request.query_params)
        
        logger.info(f"Received Robokassa fail: {params}")
        
        # Обновляем статус платежа
        invoice_id = params.get('InvId')
        if invoice_id:
            result = await db.execute(
                select(Payment).where(Payment.robokassa_invoice_id == invoice_id)
            )
            payment = result.scalar_one_or_none()
            
            if payment:
                payment.status = PaymentStatus.FAILED
                payment.failure_reason = "Payment failed in Robokassa"
                payment.processed_at = datetime.now(timezone.utc)
                await db.commit()
        
        return JSONResponse(content={
            "status": "error",
            "message": "Платеж не был завершен",
            "invoice_id": invoice_id
        })
        
    except Exception as e:
        logger.error(f"Error processing Robokassa fail: {e}")
        return JSONResponse(
            content={"status": "error", "message": "Ошибка обработки"},
            status_code=500
        )

async def process_robokassa_payment(params: Dict[str, Any], db: AsyncSession):
    """
    Обработка платежа от Робокассы в фоновом режиме
    
    Args:
        params: Параметры от Робокассы
        db: Сессия базы данных
    """
    try:
        invoice_id = params.get('InvId')
        amount = float(params.get('OutSum', 0))
        
        # Находим платеж (сначала по external_id для новой системы, затем по robokassa_invoice_id для старой)
        result = await db.execute(
            select(Payment).where(Payment.external_id == invoice_id)
        )
        payment = result.scalar_one_or_none()
        
        # Если не найдено, попробуем старую систему
        if not payment:
            result = await db.execute(
                select(Payment).where(Payment.robokassa_invoice_id == invoice_id)
            )
            payment = result.scalar_one_or_none()
        
        if not payment:
            logger.warning(f"Payment not found for invoice {invoice_id}")
            return
        
        # Проверяем, не был ли платеж уже обработан
        if payment.status == PaymentStatus.SUCCEEDED:
            logger.info(f"Payment {payment.id} already processed")
            return
        
        # Обновляем статус платежа
        payment.status = PaymentStatus.SUCCEEDED
        payment.paid_at = datetime.now(timezone.utc)
        payment.processed_at = datetime.now(timezone.utc)
        payment.robokassa_signature = params.get('SignatureValue')
        payment.robokassa_payment_method = params.get('PaymentMethod')
        payment.external_data = params
        
        await db.commit()
        
        # Активируем подписку
        subscription_service = SubscriptionService(db)
        metadata = payment.payment_metadata or {}
        subscription_type = metadata.get('subscription_type')
        
        if subscription_type:
            result = await subscription_service.activate_subscription(
                user_id=payment.user_id,
                subscription_type=subscription_type,
                payment_id=payment.id
            )
            
            if result.get('status') == 'success':
                logger.info(f"Subscription activated for user {payment.user_id}")
            else:
                logger.error(f"Failed to activate subscription: {result.get('message')}")
        
        logger.info(f"Successfully processed payment {payment.id}")
        
    except Exception as e:
        logger.error(f"Error processing Robokassa payment: {e}")
        await db.rollback()

async def get_active_provider_by_type(db: AsyncSession, provider_type: Optional[str]) -> Optional[PaymentProvider]:
    """Получение активного провайдера определенного типа из БД"""
    if not provider_type:
        # Если тип не указан, берем первый доступный активный провайдер
        result = await db.execute(
            select(PaymentProvider).where(
                PaymentProvider.is_active == True
            ).order_by(PaymentProvider.priority.asc())
        )
        return result.scalar_one_or_none()
    
    try:
        # Преобразуем строку в enum
        enum_type = PaymentProviderType(provider_type)
        result = await db.execute(
            select(PaymentProvider).where(
                PaymentProvider.provider_type == enum_type,
                PaymentProvider.is_active == True
            ).order_by(PaymentProvider.priority.asc())
        )
        return result.scalar_one_or_none()
    except ValueError:
        logger.warning(f"Unknown provider type: {provider_type}")
        return None

async def get_robokassa_provider(db: AsyncSession) -> Optional[PaymentProvider]:
    """Получение активного Robokassa провайдера из БД"""
    result = await db.execute(
        select(PaymentProvider).where(
            PaymentProvider.provider_type == PaymentProviderType.robokassa,
            PaymentProvider.is_active == True
        ).order_by(PaymentProvider.priority.asc())
    )
    return result.scalar_one_or_none()

async def get_robokassa_service(db: AsyncSession) -> RobokassaService:
    """Получение сервиса Robokassa с конфигурацией из БД"""
    provider = await get_robokassa_provider(db)
    if not provider:
        logger.error("No active Robokassa provider found in database")
        raise HTTPException(status_code=500, detail="Robokassa провайдер не настроен в системе")
    
    provider_config = provider.get_robokassa_config()
    return RobokassaService(provider_config=provider_config)


@router.get("/providers/active")
async def get_active_payment_providers(
    db: AsyncSession = Depends(get_db)
):
    """Получение списка активных платежных провайдеров для бота"""
    try:
        # Получаем активные провайдеры из БД
        result = await db.execute(
            select(PaymentProvider).where(
                PaymentProvider.is_active == True
            ).order_by(PaymentProvider.priority.asc())
        )
        providers = result.scalars().all()
        
        if not providers:
            logger.warning("No active payment providers found")
            return JSONResponse(
                content={"status": "error", "message": "Нет активных платежных провайдеров"},
                status_code=404
            )
        
        # Формируем ответ для бота
        active_providers = []
        for provider in providers:
            provider_info = {
                "id": provider.id,
                "name": provider.name,
                "provider_type": provider.provider_type.value,
                "is_default": provider.is_default,
                "min_amount": float(provider.min_amount) if provider.min_amount else None,
                "max_amount": float(provider.max_amount) if provider.max_amount else None,
                "commission_percent": float(provider.commission_percent) if provider.commission_percent else None,
                "commission_fixed": float(provider.commission_fixed) if provider.commission_fixed else None
            }
            active_providers.append(provider_info)
        
        logger.info(f"Found {len(active_providers)} active payment providers")
        
        return JSONResponse(content={
            "status": "success",
            "providers": active_providers,
            "total": len(active_providers)
        })
        
    except Exception as e:
        logger.error(f"Error getting active payment providers: {e}")
        return JSONResponse(
            content={"status": "error", "message": "Ошибка получения провайдеров"},
            status_code=500
        ) 