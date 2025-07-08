from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from config.database import get_db
from models.user import User
from models.payment import Payment, PaymentStatus
from services.auth_service import get_current_user

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/profile")
async def get_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Получить профиль текущего пользователя"""
    return {
        "id": current_user.id,
        "telegram_id": current_user.telegram_id,
        "username": current_user.username,
        "is_active": current_user.is_active,
        "created_at": current_user.created_at
    }

@router.get("/me")
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """Получить информацию о текущем пользователе"""
    return {
        "id": current_user.id,
        "telegram_id": current_user.telegram_id,
        "username": current_user.username,
        "status": "active" if current_user.is_active else "inactive"
    }

@router.get("/telegram/{telegram_id}")
async def get_user_by_telegram_id(
    telegram_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Получить пользователя по Telegram ID"""
    try:
        result = await db.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        return {
            "id": user.id,
            "telegram_id": user.telegram_id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "is_active": user.is_active,
            "subscription_status": user.subscription_status if user.subscription_status else "none",
            "valid_until": user.valid_until.isoformat() if user.valid_until else None,
            "created_at": user.created_at.isoformat() if user.created_at else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Ошибка получения пользователя")

@router.get("/telegram/{telegram_id}/pending-payments")
async def get_user_pending_payments(
    telegram_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Получить неоплаченные платежи пользователя"""
    try:
        # Найти пользователя
        result = await db.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        # Получить неоплаченные платежи
        payments_result = await db.execute(
            select(Payment).where(
                Payment.user_id == user.id,
                Payment.status == PaymentStatus.PENDING
            ).order_by(Payment.created_at.desc())
        )
        payments = payments_result.scalars().all()
        
        return {
            "user_id": user.id,
            "telegram_id": telegram_id,
            "pending_payments": [
                {
                    "id": payment.id,
                    "amount": payment.amount,
                    "currency": payment.currency,
                    "description": payment.description,
                    "confirmation_url": payment.confirmation_url,
                    "created_at": payment.created_at.isoformat() if payment.created_at else None,
                    "payment_metadata": payment.payment_metadata
                }
                for payment in payments
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Ошибка получения платежей")

@router.post("/telegram/{telegram_id}/cancel-pending-payments")
async def cancel_user_pending_payments(
    telegram_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Отменить все неоплаченные платежи пользователя"""
    try:
        # Найти пользователя
        result = await db.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        # Отменить все неоплаченные платежи
        from sqlalchemy import update
        await db.execute(
            update(Payment).where(
                Payment.user_id == user.id,
                Payment.status == PaymentStatus.PENDING
            ).values(status=PaymentStatus.CANCELLED)
        )
        
        await db.commit()
        
        return {
            "status": "success",
            "message": "Все неоплаченные платежи отменены"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Ошибка отмены платежей") 