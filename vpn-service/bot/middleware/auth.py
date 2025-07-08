"""
Authentication middleware for VPN Telegram Bot
"""
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update, Message, CallbackQuery
import structlog

logger = structlog.get_logger(__name__)

class AuthMiddleware(BaseMiddleware):
    """
    Middleware для аутентификации и логирования пользователей
    """
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """
        Обработка события перед передачей в handler
        """
        try:
            # Получаем информацию о пользователе
            user_id = None
            username = None
            
            if isinstance(event, (Message, CallbackQuery)):
                user_id = event.from_user.id if event.from_user else None
                username = event.from_user.username if event.from_user else None
                
                # Логируем активность пользователя
                if user_id:
                    logger.info(
                        "User activity",
                        user_id=user_id,
                        username=username,
                        event_type=type(event).__name__
                    )
                    
                    # Сохраняем ID пользователя в данных для handler'ов
                    data['user_id'] = user_id
                    data['username'] = username
            
            # Продолжаем обработку
            return await handler(event, data)
            
        except Exception as e:
            logger.error(
                "Auth middleware error",
                user_id=user_id,
                username=username,
                error=str(e)
            )
            # Даже если произошла ошибка в middleware, продолжаем обработку
            return await handler(event, data) 