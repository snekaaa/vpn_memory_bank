"""
VPN Memory Bank - FastAPI Application
Main application file with API endpoints
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import hashlib
import asyncio
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="VPN Memory Bank API",
    description="API для управления VPN подписками и платежами",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class UserCreate(BaseModel):
    telegram_id: int = Field(..., gt=0, description="Telegram ID пользователя")
    username: Optional[str] = Field(None, description="Имя пользователя в Telegram")
    first_name: Optional[str] = Field(None, description="Имя")
    last_name: Optional[str] = Field(None, description="Фамилия")
    language_code: str = Field("ru", description="Код языка")

class PaymentCreate(BaseModel):
    user_id: int = Field(..., gt=0, description="ID пользователя")
    subscription_type: str = Field(..., description="Тип подписки")
    provider_type: str = Field("robokassa", description="Провайдер платежей")
    enable_autopay: bool = Field(False, description="Включить автоплатеж")
    user_email: Optional[str] = Field(None, description="Email пользователя")

class AppSettings(BaseModel):
    trial_enabled: bool = Field(True, description="Включен ли триал")
    trial_days: int = Field(3, description="Количество дней триала")
    auto_renewal_enabled: bool = Field(True, description="Включено ли автопродление")

# In-memory storage (for demo purposes)
users_db: Dict[int, Dict[str, Any]] = {}
payments_db: Dict[int, Dict[str, Any]] = {}
settings_db: Dict[str, Any] = {
    "trial_enabled": True,
    "trial_days": 3,
    "auto_renewal_enabled": True
}

# Helper functions - эти методы мы будем рефакторить

def validate_payment_data(payment_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Старый метод валидации платежных данных - требует рефакторинга
    Этот метод слишком сложный и делает много разных вещей
    """
    errors = []
    
    # Проверка обязательных полей
    if not payment_data.get("user_id"):
        errors.append("user_id is required")
    elif not isinstance(payment_data["user_id"], int) or payment_data["user_id"] <= 0:
        errors.append("user_id must be positive integer")
    
    # Проверка типа подписки
    if not payment_data.get("subscription_type"):
        errors.append("subscription_type is required")
    elif payment_data["subscription_type"] not in ["weekly", "monthly", "quarterly", "yearly"]:
        errors.append("invalid subscription_type")
    
    # Проверка провайдера
    if not payment_data.get("provider_type"):
        errors.append("provider_type is required")
    elif payment_data["provider_type"] not in ["robokassa", "freekassa", "yookassa", "coingate"]:
        errors.append("invalid provider_type")
    
    # Проверка email (если указан)
    if payment_data.get("user_email"):
        email = payment_data["user_email"]
        if "@" not in email or "." not in email or len(email) < 5:
            errors.append("invalid email format")
    
    # Проверка автоплатежа
    if "enable_autopay" in payment_data:
        if not isinstance(payment_data["enable_autopay"], bool):
            errors.append("enable_autopay must be boolean")
        
        # Проверяем поддержку автоплатежей провайдером
        provider = payment_data.get("provider_type")
        autopay_supported = provider in ["robokassa", "yookassa"]
        if payment_data["enable_autopay"] and not autopay_supported:
            errors.append(f"Provider {provider} does not support autopay")
    
    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
        "validated_data": payment_data if len(errors) == 0 else None
    }

def calculate_payment_amount(subscription_type: str) -> float:
    """
    Старый метод расчета суммы платежа - требует рефакторинга
    Слишком много условий и магических чисел
    """
    if subscription_type == "weekly":
        return 200.0
    elif subscription_type == "monthly":
        return 500.0
    elif subscription_type == "quarterly":
        return 1200.0
    elif subscription_type == "yearly":
        return 4000.0
    else:
        raise ValueError(f"Unknown subscription type: {subscription_type}")

def generate_payment_url(provider: str, payment_id: int, amount: float) -> str:
    """
    Старый метод генерации URL платежа - требует рефакторинга
    Много дублированного кода и жестко зашитых значений
    """
    if provider == "robokassa":
        return f"https://robokassa.ru/Merchant/Index.aspx?MerchantLogin=vpn-bezlagov&OutSum={amount}&InvId={payment_id}&Description=VPN+Subscription"
    elif provider == "freekassa":
        return f"https://pay.freekassa.ru/?m=12345&oa={amount}&o={payment_id}&s=signature_hash"
    elif provider == "yookassa":
        return f"https://yookassa.ru/checkout?amount={amount}&order_id={payment_id}"
    elif provider == "coingate":
        return f"https://coingate.com/invoice/create?price_amount={amount}&order_id={payment_id}"
    else:
        raise ValueError(f"Unknown payment provider: {provider}")

def create_vpn_key(user_id: int, country: str = "US") -> Dict[str, Any]:
    """
    Метод создания VPN ключа - тоже требует улучшения
    """
    key_id = f"vpn_key_{user_id}_{datetime.now().timestamp()}"
    config = f"vless://generated-config-for-user-{user_id}@server.example.com:443"
    
    return {
        "key_id": key_id,
        "user_id": user_id,
        "status": "active",
        "country": country,
        "config": config,
        "created_at": datetime.now().isoformat(),
        "expires_at": (datetime.now() + timedelta(days=30)).isoformat()
    }

# API Endpoints

@app.get("/")
async def root():
    """Базовый endpoint для проверки работоспособности"""
    return {
        "message": "VPN Memory Bank API",
        "version": "1.0.0",
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/v1/app/settings")
async def get_app_settings():
    """Получение настроек приложения"""
    return {
        "status": "success",
        "data": settings_db
    }

@app.post("/api/v1/users/full-cycle")
async def create_user_full_cycle(user_data: UserCreate):
    """
    Полный цикл создания пользователя с подпиской и VPN ключом
    """
    try:
        telegram_id = user_data.telegram_id
        
        # Проверяем, существует ли пользователь
        if telegram_id in users_db:
            return {
                "success": True,
                "message": "Пользователь уже существует",
                "operations_completed": {
                    "user_created": False,
                    "subscription_created": False,
                    "vpn_key_created": False,
                    "notification_sent": True
                },
                "user": users_db[telegram_id]
            }
        
        # Создаем пользователя
        user = {
            "telegram_id": telegram_id,
            "username": user_data.username,
            "first_name": user_data.first_name,
            "last_name": user_data.last_name,
            "language_code": user_data.language_code,
            "subscription_active": False,
            "subscription_days_left": 0,
            "is_trial": False,
            "created_at": datetime.now().isoformat()
        }
        
        operations_completed = {
            "user_created": True,
            "subscription_created": False,
            "vpn_key_created": False,
            "notification_sent": True
        }
        
        # Проверяем настройки триала
        if settings_db.get("trial_enabled", False):
            trial_days = settings_db.get("trial_days", 3)
            user.update({
                "subscription_active": True,
                "subscription_days_left": trial_days,
                "is_trial": True
            })
            operations_completed["subscription_created"] = True
            
            # Создаем VPN ключ для триала
            vpn_key = create_vpn_key(telegram_id)
            operations_completed["vpn_key_created"] = True
        else:
            vpn_key = None
        
        users_db[telegram_id] = user
        
        return {
            "success": True,
            "operations_completed": operations_completed,
            "user": user,
            "vpn_key": vpn_key
        }
        
    except Exception as e:
        logger.error(f"Error in full-cycle creation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/users/{telegram_id}/dashboard")
async def get_user_dashboard(telegram_id: int):
    """Получение dashboard пользователя"""
    if telegram_id not in users_db:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    user = users_db[telegram_id]
    
    # Генерируем mock VPN ключи для активных пользователей
    vpn_keys = []
    if user.get("subscription_active", False):
        vpn_keys = [create_vpn_key(telegram_id)]
    
    return {
        "user": user,
        "vpn_keys": vpn_keys,
        "subscription": {
            "plan_name": "Trial" if user.get("is_trial") else "Monthly",
            "auto_renewal": settings_db.get("auto_renewal_enabled", False),
            "trial": user.get("is_trial", False)
        }
    }

@app.post("/api/v1/payments/create")
async def create_payment(payment_data: PaymentCreate):
    """
    Создание платежа - ОТРЕФАКТОРЕНО! Теперь использует улучшенный PaymentService
    """
    try:
        # Импортируем улучшенный сервис
        from utils import PaymentService
        
        # Создаем экземпляр сервиса
        payment_service = PaymentService()
        
        # Используем новый улучшенный метод создания платежа
        payment_result = payment_service.create_payment(payment_data.dict())
        
        # Сохраняем в базу данных
        payment_id = payment_result["payment_id"]
        payment = {
            "payment_id": payment_id,
            "user_id": payment_data.user_id,
            "subscription_type": payment_data.subscription_type,
            "provider_type": payment_data.provider_type,
            "amount": payment_result["amount"],
            "currency": payment_result["currency"],
            "status": "created",
            "payment_url": payment_result["payment_url"],
            "subscription_info": payment_result["subscription_info"],
            "created_at": datetime.now().isoformat()
        }
        
        payments_db[payment_id] = payment
        
        # Возвращаем улучшенный ответ
        return {
            "status": "success",
            "payment_id": payment_id,
            "payment_url": payment_result["payment_url"],
            "amount": payment_result["amount"],
            "currency": payment_result["currency"],
            "subscription_info": payment_result["subscription_info"],
            "provider": payment_result["provider"]
        }
        
    except ValueError as e:
        # Теперь у нас более детальные ошибки валидации
        raise HTTPException(status_code=400, detail={
            "message": "Payment creation failed",
            "error": str(e),
            "type": "validation_error"
        })
    except Exception as e:
        logger.error(f"Error creating payment: {e}")
        raise HTTPException(status_code=500, detail={
            "message": "Internal server error",
            "error": str(e),
            "type": "internal_error"
        })

@app.post("/api/v1/webhooks/yookassa")
async def yookassa_webhook(webhook_data: Dict[str, Any]):
    """Webhook для обработки уведомлений от YooKassa"""
    try:
        if webhook_data.get("event") == "payment.succeeded":
            payment_id = int(webhook_data["object"]["metadata"]["order_id"])
            if payment_id in payments_db:
                payments_db[payment_id]["status"] = "succeeded"
                logger.info(f"Payment {payment_id} succeeded via YooKassa")
        
        return "OK"
    except Exception as e:
        logger.error(f"YooKassa webhook error: {e}")
        raise HTTPException(status_code=400, detail="Webhook processing failed")

@app.post("/api/v1/webhooks/freekassa")
async def freekassa_webhook(webhook_data: Dict[str, Any]):
    """Webhook для обработки уведомлений от FreeKassa"""
    try:
        # Проверяем подпись (упрощенная версия)
        merchant_id = webhook_data.get("MERCHANT_ID")
        amount = webhook_data.get("AMOUNT")
        order_id = webhook_data.get("MERCHANT_ORDER_ID")
        
        if merchant_id and amount and order_id:
            payment_id = int(order_id.replace("order_", ""))
            if payment_id in payments_db:
                payments_db[payment_id]["status"] = "succeeded"
                logger.info(f"Payment {payment_id} succeeded via FreeKassa")
        
        return "YES"
    except Exception as e:
        logger.error(f"FreeKassa webhook error: {e}")
        raise HTTPException(status_code=400, detail="Webhook processing failed")

@app.post("/api/v1/webhooks/coingate")
async def coingate_webhook(webhook_data: Dict[str, Any]):
    """Webhook для обработки уведомлений от CoinGate"""
    try:
        if webhook_data.get("status") == "paid":
            order_id = webhook_data.get("order_id", "").replace("order_", "")
            if order_id.isdigit():
                payment_id = int(order_id)
                if payment_id in payments_db:
                    payments_db[payment_id]["status"] = "succeeded"
                    logger.info(f"Payment {payment_id} succeeded via CoinGate")
        
        return "OK"
    except Exception as e:
        logger.error(f"CoinGate webhook error: {e}")
        raise HTTPException(status_code=400, detail="Webhook processing failed")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)