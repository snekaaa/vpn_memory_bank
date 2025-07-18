"""
API эндпоинты для работы с автоплатежами
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict, Any
import logging

from config.database import get_db
from models.user import User
from models.auto_payment import AutoPayment
from models.subscription import Subscription
from services.auto_payment_service import AutoPaymentService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/users", tags=["Auto Payments"])

@router.get("/{telegram_id}/auto_payment_info")
async def get_user_auto_payment_info(
    telegram_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Получение информации об автоплатеже пользователя по telegram_id"""
    try:
        # Находим пользователя по telegram_id
        result = await db.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            return {
                'enabled': False,
                'message': 'Пользователь не найден'
            }
        
        # Получаем информацию об автоплатеже
        auto_payment_service = AutoPaymentService(db)
        auto_payment_info = await auto_payment_service.get_user_auto_payment_info(user.id)
        
        return auto_payment_info
        
    except Exception as e:
        logger.error(f"Error getting auto payment info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка получения информации об автоплатеже"
        )

@router.get("/{telegram_id}/subscription_status")
async def get_user_subscription_status(
    telegram_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Получение статуса подписки пользователя по telegram_id"""
    try:
        # Находим пользователя по telegram_id
        result = await db.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            return {
                'success': False,
                'message': 'Пользователь не найден'
            }
        
        # Проверяем активную подписку по данным пользователя
        if not user.has_active_subscription:
            return {
                'success': False,
                'message': 'Активная подписка не найдена'
            }
        
        # Форматируем дату окончания
        end_date_str = user.valid_until.strftime('%d.%m.%Y') if user.valid_until else 'Не определена'
        
        return {
            'success': True,
            'plan_name': 'VPN подписка',  # Временно статическое значение
            'end_date': end_date_str,
            'days_remaining': user.subscription_days_remaining,
            'subscription_type': 'active',
            'has_autopay': False  # Временно статическое значение
        }
        
    except Exception as e:
        logger.error(f"Error getting subscription status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка получения статуса подписки"
        )

@router.post("/{telegram_id}/auto_payment/disable")
async def disable_user_auto_payment(
    telegram_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Отключение автоплатежа пользователя по telegram_id"""
    try:
        # Находим пользователя по telegram_id
        result = await db.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            return {
                'success': False,
                'message': 'Пользователь не найден'
            }
        
        # Отключаем автоплатеж
        auto_payment_service = AutoPaymentService(db)
        result = await auto_payment_service.cancel_auto_payment(user.id)
        
        return result
        
    except Exception as e:
        logger.error(f"Error disabling auto payment: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка отключения автоплатежа"
        )


@router.post("/{telegram_id}/auto_payment/enable")
async def enable_user_auto_payment(
    telegram_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Включение автоплатежа пользователя по telegram_id"""
    try:
        # Находим пользователя по telegram_id
        result = await db.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            return {
                'success': False,
                'message': 'Пользователь не найден'
            }
        
        # Включаем автоплатеж
        auto_payment_service = AutoPaymentService(db)
        result = await auto_payment_service.enable_auto_payment(user.id)
        
        return result
        
    except Exception as e:
        logger.error(f"Error enabling auto payment: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка включения автоплатежа"
        )

@router.get("/{telegram_id}/pending_payments")
async def get_user_pending_payments(
    telegram_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Получение неоплаченных платежей пользователя"""
    try:
        # Находим пользователя по telegram_id
        result = await db.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            return {
                'pending_payments': []
            }
        
        # Импортируем здесь, чтобы избежать циклических зависимостей
        from models.payment import Payment, PaymentStatus
        
        # Получаем неоплаченные платежи
        payments_result = await db.execute(
            select(Payment).where(
                Payment.user_id == user.id,
                Payment.status == PaymentStatus.PENDING
            ).order_by(Payment.created_at.desc())
        )
        payments = payments_result.scalars().all()
        
        pending_payments = []
        for payment in payments:
            pending_payments.append({
                'id': payment.id,
                'amount': payment.amount,
                'currency': payment.currency,
                'description': payment.description,
                'confirmation_url': payment.confirmation_url,
                'payment_metadata': payment.payment_metadata,
                'created_at': payment.created_at.isoformat() if payment.created_at else None
            })
        
        return {
            'pending_payments': pending_payments
        }
        
    except Exception as e:
        logger.error(f"Error getting pending payments: {e}")
        return {
            'pending_payments': []
        } 