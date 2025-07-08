from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from config.database import get_db
from models.user import User
from services.auth_service import get_current_user

router = APIRouter(prefix="/vpn-keys", tags=["vpn-keys"])

@router.get("/")
async def get_user_vpn_keys(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Получить VPN ключи пользователя"""
    return {
        "user_id": current_user.id,
        "vpn_keys": [],
        "message": "VPN keys functionality not implemented yet"
    }

@router.post("/create")
async def create_vpn_key(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Создать новый VPN ключ"""
    return {
        "user_id": current_user.id,
        "vpn_key": None,
        "message": "VPN key creation not implemented yet"
    } 