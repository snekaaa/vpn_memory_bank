from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from config.database import get_db
from models.user import User
from services.auth_service import get_current_user

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])

@router.get("/")
async def get_user_subscriptions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Получить подписки пользователя"""
    return {
        "user_id": current_user.id,
        "subscriptions": [],
        "message": "Subscriptions functionality not implemented yet"
    }

@router.get("/active")
async def get_active_subscription(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Получить активную подписку пользователя"""
    return {
        "user_id": current_user.id,
        "active_subscription": None,
        "message": "Active subscription check not implemented yet"
    } 