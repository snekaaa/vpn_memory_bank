"""
API эндпоинты для работы с автоплатежами
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict, Any
from datetime import datetime, timezone
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
        logger.info(f"Getting auto payment info for user with telegram_id: {telegram_id}")
        
        # Используем новый метод для получения информации по telegram_id
        auto_payment_service = AutoPaymentService(db)
        auto_payment_info = await auto_payment_service.get_user_auto_payment_info_by_telegram_id(telegram_id)
        
        # Добавляем флаг успеха в ответ
        auto_payment_info['success'] = True
        
        # Логируем результат
        logger.info(f"Auto payment info retrieved for user {telegram_id}: enabled={auto_payment_info.get('enabled')}, is_default={auto_payment_info.get('is_default')}")
        return auto_payment_info
        
    except Exception as e:
        logger.error(f"Error getting auto payment info for user {telegram_id}: {e}", exc_info=True)
        # Возвращаем структурированный ответ с fallback значением по умолчанию
        return {
            'enabled': True,  # Default value as per requirements
            'message': 'Ошибка получения информации об автоплатеже, используется значение по умолчанию',
            'success': False,
            'is_default': True,
            'error': str(e),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

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
        logger.info(f"Disabling auto payment for user with telegram_id: {telegram_id}")
        
        # Находим пользователя по telegram_id
        result = await db.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            logger.warning(f"User with telegram_id {telegram_id} not found when disabling auto payment")
            return {
                'success': False,
                'message': 'Пользователь не найден',
                'code': 'user_not_found'
            }
        
        # Отключаем автоплатеж независимо от статуса подписки
        # Явно логируем, что мы обрабатываем пользователя независимо от статуса подписки
        has_subscription = user.has_active_subscription
        logger.info(f"Disabling auto payment for user {telegram_id} with subscription status: {user.subscription_status}, has_active_subscription: {has_subscription}")
        
        auto_payment_service = AutoPaymentService(db)
        result = await auto_payment_service.cancel_auto_payment(user.id)
        
        # Добавляем информацию о статусе подписки в ответ
        if result.get('success'):
            result['subscription_status'] = user.subscription_status
            result['has_active_subscription'] = has_subscription
            logger.info(f"Auto payment successfully disabled for user {telegram_id}")
        else:
            logger.warning(f"Failed to disable auto payment for user {telegram_id}: {result.get('message')}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error disabling auto payment for user {telegram_id}: {e}", exc_info=True)
        # Возвращаем структурированный ответ вместо исключения для лучшей обработки на стороне клиента
        return {
            'success': False,
            'message': 'Ошибка отключения автоплатежа',
            'error': str(e),
            'code': 'internal_error'
        }


@router.post("/{telegram_id}/auto_payment/enable")
async def enable_user_auto_payment(
    telegram_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Включение автоплатежа пользователя по telegram_id"""
    try:
        logger.info(f"Enabling auto payment for user with telegram_id: {telegram_id}")
        
        # Находим пользователя по telegram_id
        result = await db.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            logger.warning(f"User with telegram_id {telegram_id} not found when enabling auto payment")
            return {
                'success': False,
                'message': 'Пользователь не найден',
                'code': 'user_not_found'
            }
        
        # Включаем автоплатеж независимо от статуса подписки
        # Явно логируем, что мы обрабатываем пользователя независимо от статуса подписки
        has_subscription = user.has_active_subscription
        logger.info(f"Enabling auto payment for user {telegram_id} with subscription status: {user.subscription_status}, has_active_subscription: {has_subscription}")
        
        auto_payment_service = AutoPaymentService(db)
        result = await auto_payment_service.enable_auto_payment(user.id)
        
        # Добавляем информацию о статусе подписки в ответ
        if result.get('success'):
            result['subscription_status'] = user.subscription_status
            result['has_active_subscription'] = has_subscription
            logger.info(f"Auto payment successfully enabled for user {telegram_id}")
        else:
            logger.warning(f"Failed to enable auto payment for user {telegram_id}: {result.get('message')}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error enabling auto payment for user {telegram_id}: {e}", exc_info=True)
        # Возвращаем структурированный ответ вместо исключения для лучшей обработки на стороне клиента
        return {
            'success': False,
            'message': 'Ошибка включения автоплатежа',
            'error': str(e),
            'code': 'internal_error'
        }

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