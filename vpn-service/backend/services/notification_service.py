import asyncio
import aiohttp
from typing import Optional, Dict, Any
import structlog
from datetime import datetime

from config.settings import get_settings

logger = structlog.get_logger(__name__)

class NotificationService:
    """Сервис для отправки уведомлений пользователям"""
    
    def __init__(self):
        self.settings = get_settings()
        self.bot_token = self.settings.telegram_bot_token
        
    async def send_payment_success_notification(
        self, 
        telegram_id: int, 
        payment_amount: float, 
        subscription_type: str,
        vpn_key_name: str
    ):
        """Отправка уведомления об успешной оплате"""
        try:
            message = f"""
✅ <b>Платеж успешно обработан!</b>

💰 <b>Сумма:</b> {payment_amount:.2f}₽
📋 <b>Подписка:</b> {subscription_type}
🔑 <b>VPN ключ:</b> {vpn_key_name}

🎉 Ваша подписка активирована! Теперь вы можете получить конфигурацию VPN в разделе "🔐 Мой VPN".

⚡ Скорость подключения: до 1 Гбит/с
🛡️ Протокол: VLESS + XTLS-REALITY
🌍 Безлимитный трафик

Спасибо за покупку! 🙏
"""
            
            await self._send_telegram_message(telegram_id, message)
            
            logger.info("Payment success notification sent", 
                       telegram_id=telegram_id,
                       amount=payment_amount,
                       subscription_type=subscription_type)
            
        except Exception as e:
            logger.error("Failed to send payment success notification", 
                        telegram_id=telegram_id,
                        error=str(e))
    
    async def send_payment_failed_notification(
        self, 
        telegram_id: int, 
        payment_amount: float, 
        subscription_type: str,
        failure_reason: Optional[str] = None
    ):
        """Отправка уведомления о неудачной оплате"""
        try:
            message = f"""
❌ <b>Платеж не прошел</b>

💰 <b>Сумма:</b> {payment_amount:.2f}₽
📋 <b>Подписка:</b> {subscription_type}
"""
            
            if failure_reason:
                message += f"\n📝 <b>Причина:</b> {failure_reason}"
            
            message += """

💡 <b>Что делать:</b>
• Проверьте данные карты
• Убедитесь, что на карте достаточно средств
• Попробуйте другой способ оплаты
• Обратитесь в поддержку: /help

🔄 Попробовать оплатить снова: /start
"""
            
            await self._send_telegram_message(telegram_id, message)
            
            logger.info("Payment failed notification sent", 
                       telegram_id=telegram_id,
                       amount=payment_amount,
                       subscription_type=subscription_type)
            
        except Exception as e:
            logger.error("Failed to send payment failed notification", 
                        telegram_id=telegram_id,
                        error=str(e))
    
    async def send_subscription_expiring_notification(
        self, 
        telegram_id: int, 
        subscription_type: str,
        days_remaining: int
    ):
        """Отправка уведомления о скором истечении подписки"""
        try:
            if days_remaining <= 1:
                urgency = "🔴 <b>СРОЧНО!</b>"
                action_text = "истекает сегодня"
            elif days_remaining <= 3:
                urgency = "🟡 <b>ВНИМАНИЕ!</b>"
                action_text = f"истекает через {days_remaining} дня"
            else:
                urgency = "🔔 <b>Напоминание</b>"
                action_text = f"истекает через {days_remaining} дней"
            
            message = f"""
{urgency}

📋 <b>Ваша подписка {subscription_type} {action_text}</b>

💡 <b>Что нужно сделать:</b>
• Продлите подписку, чтобы не потерять доступ к VPN
• Выберите подходящий тариф: /start
• При продлении — дополнительная скидка 10%!

🎁 <b>Бонус при продлении:</b>
• Скидка 10% на любой тариф
• Приоритетная поддержка
• Уведомления о новых серверах

💳 Продлить подписку: /start
"""
            
            await self._send_telegram_message(telegram_id, message)
            
            logger.info("Subscription expiring notification sent", 
                       telegram_id=telegram_id,
                       subscription_type=subscription_type,
                       days_remaining=days_remaining)
            
        except Exception as e:
            logger.error("Failed to send subscription expiring notification", 
                        telegram_id=telegram_id,
                        error=str(e))
    
    async def send_vpn_key_created_notification(
        self, 
        telegram_id: int, 
        vpn_key_name: str,
        server_location: str
    ):
        """Отправка уведомления о создании VPN ключа"""
        try:
            message = f"""
🔑 <b>VPN ключ создан!</b>

🔐 <b>Ключ:</b> {vpn_key_name}
🌍 <b>Сервер:</b> {server_location}
⚡ <b>Протокол:</b> VLESS + XTLS-REALITY

💾 <b>Получить конфигурацию:</b>
• Откройте раздел "🔐 Мой VPN"
• Нажмите "📄 Получить конфигурацию"
• Или "📱 QR-код" для быстрой настройки

📱 <b>Поддерживаемые приложения:</b>
• V2rayN (Windows)
• V2rayNG (Android)
• FairVPN (iOS)
• Qv2ray (Linux)

❓ Нужна помощь с настройкой? /help
"""
            
            await self._send_telegram_message(telegram_id, message)
            
            logger.info("VPN key created notification sent", 
                       telegram_id=telegram_id,
                       vpn_key_name=vpn_key_name,
                       server_location=server_location)
            
        except Exception as e:
            logger.error("Failed to send VPN key created notification", 
                        telegram_id=telegram_id,
                        error=str(e))
    
    async def send_subscription_expired_notification(
        self, 
        telegram_id: int, 
        subscription_type: str
    ):
        """Отправка уведомления об истечении подписки"""
        try:
            message = f"""
⏰ <b>Подписка истекла</b>

📋 <b>Подписка:</b> {subscription_type}
📅 <b>Дата истечения:</b> {datetime.now().strftime('%d.%m.%Y')}

🔒 <b>Доступ к VPN приостановлен</b>

💡 <b>Что делать:</b>
• Продлите подписку для восстановления доступа
• Выберите новый тариф: /start
• Специальная скидка 15% для возвращающихся клиентов!

🎁 <b>Акция для вас:</b>
• Скидка 15% на любой тариф
• Бесплатная смена сервера
• Приоритетная поддержка

💳 Восстановить доступ: /start
"""
            
            await self._send_telegram_message(telegram_id, message)
            
            logger.info("Subscription expired notification sent", 
                       telegram_id=telegram_id,
                       subscription_type=subscription_type)
            
        except Exception as e:
            logger.error("Failed to send subscription expired notification", 
                        telegram_id=telegram_id,
                        error=str(e))
    
    async def _send_telegram_message(self, telegram_id: int, message: str):
        """Отправка сообщения через Telegram Bot API"""
        if not self.bot_token:
            logger.warning("Bot token not configured, skipping notification")
            return
        
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        
        payload = {
            "chat_id": telegram_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=30) as response:
                    if response.status == 200:
                        logger.debug("Telegram message sent successfully", telegram_id=telegram_id)
                    else:
                        response_text = await response.text()
                        logger.error("Failed to send Telegram message", 
                                   telegram_id=telegram_id,
                                   status=response.status,
                                   response=response_text)
        except Exception as e:
            logger.error("Error sending Telegram message", 
                        telegram_id=telegram_id,
                        error=str(e))

# Создаем глобальный экземпляр сервиса
notification_service = NotificationService() 