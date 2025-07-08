from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta
from jose import JWTError, jwt
from typing import Optional
import structlog

from config.database import get_db
from config.settings import get_settings
from models.user import User

router = APIRouter()
security = HTTPBearer()
logger = structlog.get_logger(__name__)
settings = get_settings()

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Создание JWT токена"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Получение текущего пользователя по JWT токену"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(credentials.credentials, settings.secret_key, algorithms=[settings.algorithm])
        telegram_id: str = payload.get("telegram_id")
        if telegram_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    result = await db.execute(select(User).where(User.telegram_id == int(telegram_id)))
    user = result.scalar_one_or_none()
    
    if user is None:
        raise credentials_exception
    
    return user

@router.post("/telegram-auth")
async def authenticate_telegram_user(
    telegram_id: int,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    language_code: Optional[str] = "ru",
    db: AsyncSession = Depends(get_db)
):
    """Аутентификация пользователя через Telegram"""
    
    # Проверяем существующего пользователя
    result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    
    if not user:
        # Создаем нового пользователя
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            language_code=language_code
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        logger.info("New user created", telegram_id=telegram_id, username=username)
    else:
        # Обновляем информацию существующего пользователя
        user.username = username
        user.first_name = first_name
        user.last_name = last_name
        user.language_code = language_code
        user.last_activity = datetime.utcnow()
        await db.commit()
        logger.info("User updated", telegram_id=telegram_id, username=username)
    
    # Создаем токен
    access_token = create_access_token(data={"telegram_id": str(telegram_id)})
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "telegram_id": user.telegram_id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name
        }
    }

@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    """Получение информации о текущем пользователе"""
    return {
        "id": current_user.id,
        "telegram_id": current_user.telegram_id,
        "username": current_user.username,
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
        "language_code": current_user.language_code,
        "is_active": current_user.is_active,
        "created_at": current_user.created_at
    } 