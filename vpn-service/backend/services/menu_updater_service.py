"""
Сервис для автоматического обновления меню пользователей
"""

import aiohttp
import structlog
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from config.settings import get_settings

logger = structlog.get_logger(__name__)

class MenuUpdaterService:
    """Сервис для обновления меню пользователей в Telegram боте"""
    
    def __init__(self):
        self.settings = get_settings()
        self.bot_token = None
        
    async def _get_bot_token(self) -> str:
        """Получить токен бота из настроек БД"""
        if self.bot_token is None:
            try:
                from config.database import get_db_session
                from services.app_settings_service import AppSettingsService
                async with get_db_session() as db:
                    settings = await AppSettingsService.get_settings(db)
                    self.bot_token = settings.telegram_bot_token
            except Exception as e:
                logger.error(f"Error loading bot token from DB: {e}")
                # Fallback к значению по умолчанию
                self.bot_token = "8019787780:AAGy5cBWpQ09yvtDE3sp0AMY7kZyRYbSJqU"
        return self.bot_token
    
    async def _get_user_subscription_data(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """Получить данные о подписке пользователя через API"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"http://backend:8000/api/v1/integration/user-dashboard/{telegram_id}"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('success'):
                            return data.get('user', {})
                    logger.warning("Failed to get user subscription data", 
                                 telegram_id=telegram_id, 
                                 status=response.status)
                    return None
        except Exception as e:
            logger.error("Error getting user subscription data", 
                        telegram_id=telegram_id, 
                        error=str(e))
            return None
    
    def _calculate_days_remaining(self, user_data: Dict[str, Any]) -> int:
        """Вычислить количество дней до окончания подписки"""
        try:
            subscription_status = user_data.get('subscription_status', 'none')
            valid_until = user_data.get('valid_until')
            
            if subscription_status != 'active' or not valid_until:
                return 0
            
            # Парсим дату окончания подписки
            try:
                import dateutil.parser
                end_date = dateutil.parser.parse(valid_until)
            except ImportError:
                # Если dateutil недоступен, парсим вручную
                if valid_until.endswith('Z'):
                    end_date = datetime.fromisoformat(valid_until[:-1] + '+00:00')
                elif '+' in valid_until or valid_until.endswith('00:00'):
                    end_date = datetime.fromisoformat(valid_until)
                else:
                    end_date = datetime.fromisoformat(valid_until + '+00:00')
            
            # Убеждаемся что дата в UTC
            if end_date.tzinfo is None:
                end_date = end_date.replace(tzinfo=timezone.utc)
            
            # Вычисляем разность с текущим временем
            now = datetime.now(timezone.utc)
            delta = end_date - now
            
            # Возвращаем количество дней (минимум 0)
            return max(0, delta.days)
            
        except Exception as e:
            logger.error("Error calculating days remaining", 
                        user_data=user_data,
                        error=str(e))
            return 0
    
    def _create_main_menu_keyboard(self, days_remaining: int, has_active_subscription: bool) -> Dict[str, Any]:
        """Создать клавиатуру главного меню"""
        # Формируем текст кнопки подписки в зависимости от количества дней
        if days_remaining > 0:
            subscription_text = f"💳 Подписка {days_remaining} дней"
        else:
            subscription_text = "💳 Подписка"
        
        # Первая строка кнопок
        first_row = []
        
        if has_active_subscription:
            # Пользователь с активной подпиской - показываем кнопку VPN ключа
            first_row.append({"text": "🔑 Мой VPN ключ"})
        else:
            # Пользователь без подписки - показываем кнопку получения доступа
            first_row.append({"text": "🔐 Получить VPN доступ"})
        
        first_row.append({"text": subscription_text})
        
        keyboard = {
            "keyboard": [
                first_row,
                [
                    {"text": "📱 Приложения"},
                    {"text": "🧑🏼‍💻 Служба поддержки"}
                ]
            ],
            "resize_keyboard": True,
            "one_time_keyboard": False
        }
        
        return keyboard
    
    async def update_user_menu_after_payment(self, telegram_id: int) -> bool:
        """Обновить меню пользователя после успешной оплаты"""
        try:
            logger.info("🔄 Updating user menu after payment", telegram_id=telegram_id)
            
            # Получаем данные пользователя
            user_data = await self._get_user_subscription_data(telegram_id)
            if not user_data:
                logger.warning("Failed to get user data for menu update", telegram_id=telegram_id)
                return False
            
            # Вычисляем количество дней подписки
            days_remaining = self._calculate_days_remaining(user_data)
            has_active_subscription = days_remaining > 0
            
            # Создаем клавиатуру
            keyboard = self._create_main_menu_keyboard(days_remaining, has_active_subscription)
            
            # Формируем сообщение
            if has_active_subscription:
                message = (
                    "🎉 *Ваша подписка активирована!*\n\n"
                    f"✅ Подписка активна еще {days_remaining} дней\n"
                    "🔑 Теперь вы можете получить VPN ключ\n"
                    "⚡ Доступ к интернету без ограничений\n\n"
                    "Выберите действие в меню ниже:"
                )
            else:
                message = (
                    "⚠️ *Подписка истекла*\n\n"
                    "❌ Ваша подписка больше не активна\n"
                    "💳 Продлите подписку для восстановления доступа\n"
                    "🔑 VPN ключи временно недоступны\n\n"
                    "Выберите действие в меню ниже:"
                )
            
            # Отправляем обновленное меню
            success = await self._send_telegram_message_with_keyboard(telegram_id, message, keyboard)
            
            if success:
                logger.info("✅ User menu updated successfully", 
                           telegram_id=telegram_id,
                           days_remaining=days_remaining,
                           has_active_subscription=has_active_subscription)
            else:
                logger.error("❌ Failed to update user menu", telegram_id=telegram_id)
            
            return success
            
        except Exception as e:
            logger.error("💥 Error updating user menu after payment", 
                        telegram_id=telegram_id,
                        error=str(e))
            return False
    
    async def _send_telegram_message_with_keyboard(self, telegram_id: int, message: str, keyboard: Dict[str, Any]) -> bool:
        """Отправить сообщение в Telegram с клавиатурой"""
        bot_token = await self._get_bot_token()
        if not bot_token:
            logger.warning("Bot token not configured, skipping menu update")
            return False
        
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        
        payload = {
            "chat_id": telegram_id,
            "text": message,
            "parse_mode": "Markdown",
            "reply_markup": keyboard,
            "disable_web_page_preview": True
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=30) as response:
                    if response.status == 200:
                        logger.debug("Telegram message with keyboard sent successfully", telegram_id=telegram_id)
                        return True
                    else:
                        response_text = await response.text()
                        logger.error("Failed to send Telegram message with keyboard", 
                                   telegram_id=telegram_id,
                                   status=response.status,
                                   response=response_text)
                        return False
        except Exception as e:
            logger.error("Error sending Telegram message with keyboard", 
                        telegram_id=telegram_id,
                        error=str(e))
            return False

# Создаем глобальный экземпляр сервиса
menu_updater_service = MenuUpdaterService() 