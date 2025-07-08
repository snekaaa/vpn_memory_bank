from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from config.database import get_db
from models.user import User
from config.settings import get_settings

security = HTTPBearer()
settings = get_settings()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Получить текущего пользователя по JWT токену"""
    
    # Для тестирования возвращаем заглушку пользователя
    # В реальном приложении здесь должна быть валидация JWT
    
    # Создаем тестового пользователя для демонстрации
    test_user = User(
        id=1,
        telegram_id=123456789,
        username="test_user",
        is_active=True
    )
    
    # В production здесь должна быть валидация токена:
    # try:
    #     payload = jwt.decode(credentials.credentials, settings.secret_key, algorithms=[settings.algorithm])
    #     user_id = payload.get("sub")
    #     if user_id is None:
    #         raise HTTPException(status_code=401, detail="Invalid token")
    #     
    #     result = await db.execute(select(User).where(User.id == user_id))
    #     user = result.scalar_one_or_none()
    #     if user is None:
    #         raise HTTPException(status_code=401, detail="User not found")
    #     return user
    # except jwt.InvalidTokenError:
    #     raise HTTPException(status_code=401, detail="Invalid token")
    
    return test_user

def create_access_token(user_id: int) -> str:
    """Создать JWT токен доступа"""
    # Заглушка для создания токена
    # В production использовать настоящий JWT
    return f"test_token_for_user_{user_id}" 